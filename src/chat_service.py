"""
Chat Service for Sales & Inventory Copilot (PS03)
Handles natural-language query processing, intent detection, entity extraction,
deterministic service orchestration, structured evidence building, and response synthesis.
"""
import re
from typing import Dict, Any, List, Optional
from src.database import get_connection, get_products, get_stores, get_latest_date
from src.inventory_service import get_product_inventory_metrics, get_stockout_predictions
from src.sales_service import get_top_selling_products, compare_sales_periods, get_total_sales_summary
from src.recommendation_service import generate_recommendations
from src.gemini_service import generate_grounded_response, is_gemini_available
from src.rules import get_active_config
from src.schemas import ChatResponse, Recommendation, SupportingNumbers, EvidenceObject
from src.utils import setup_logger

logger = setup_logger("chat_service")

def extract_entities(question: str) -> Dict[str, Any]:
    """Extracts product mentions, store mentions, and numeric thresholds from query."""
    q = question.lower()
    
    # 1. Product matching
    products = get_products()
    matched_product = None
    for p in products:
        p_clean = re.sub(r'[^a-zA-Z0-9\s]', '', p["product_name"].lower())
        tokens = [t for t in p_clean.split() if len(t) > 3]
        if any(t in q for t in tokens):
            matched_product = p
            break

    # 2. Store matching
    stores = get_stores()
    matched_store = None
    for s in stores:
        s_clean = s["store_name"].lower()
        if any(w in q for w in s_clean.split() if len(w) > 4):
            matched_store = s
            break

    # 3. Days threshold matching (e.g. "less than 5 days", "next 7 days")
    days_match = re.search(r'(\d+)\s*(?:day|days)', q)
    extracted_days = float(days_match.group(1)) if days_match else None

    return {
        "product": matched_product,
        "store": matched_store,
        "days": extracted_days
    }

def identify_intent(question: str) -> Dict[str, Any]:
    """Classifies user question into structured analytical intent."""
    q = question.lower().strip()
    entities = extract_entities(question)

    if any(w in q for w in ["running out", "low stock", "stock out", "stockout", "out of stock", "run out"]):
        if "next week" in q or "7 days" in q or "week" in q or (entities["days"] and entities["days"] <= 7):
            return {"intent": "RUN_OUT_NEXT_WEEK", **entities}
        return {"intent": "LOW_STOCK", **entities}

    if any(w in q for w in ["overstock", "overstocked", "excess", "too much stock"]):
        return {"intent": "OVERSTOCK", **entities}

    if any(w in q for w in ["slow moving", "not moving", "stagnant", "dead stock", "idle"]):
        return {"intent": "SLOW_MOVING", **entities}

    if any(w in q for w in ["spike", "surge", "jump in sales", "rapid increase"]):
        return {"intent": "SALES_SPIKE", **entities}

    if any(w in q for w in ["why did sales decrease", "why sales drop", "why sales decrease", "why is alert", "why showing alert", "why is this product"]):
        return {"intent": "WHY_SALES_DECREASED", **entities}

    if any(w in q for w in ["drop", "declining", "decrease", "slump", "falling"]):
        return {"intent": "SALES_DROP", **entities}

    if any(w in q for w in ["sold the most", "top selling", "best seller", "highest revenue", "best-selling", "top product"]):
        return {"intent": "TOP_SELLER", **entities}

    if any(w in q for w in ["highest sales", "store generated", "which store"]):
        return {"intent": "STORE_PERFORMANCE", **entities}

    if any(w in q for w in ["needs attention", "attention today", "priority", "critical alerts", "what should i do"]):
        return {"intent": "ATTENTION_TODAY", **entities}

    if entities.get("product") or any(w in q for w in ["how did", "performance of", "sales of"]):
        return {"intent": "PRODUCT_PERFORMANCE", **entities}

    return {"intent": "GENERAL_RETAIL_QUERY", **entities}

def execute_deterministic_pipeline(intent_data: Dict[str, Any], store_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes Python deterministic calculation services based on identified intent.
    Returns structured data, evidence metadata, and recommendations.
    """
    intent = intent_data["intent"]
    product = intent_data.get("product")
    target_store_id = store_id or (intent_data.get("store", {}).get("store_id") if intent_data.get("store") else None)
    cfg = get_active_config()
    latest_date = get_latest_date()

    all_metrics = get_product_inventory_metrics(store_id=target_store_id, config=cfg)
    all_recs = generate_recommendations(store_id=target_store_id, config=cfg)

    # 1. LOW STOCK
    if intent == "LOW_STOCK":
        threshold = intent_data.get("days") or cfg.low_stock_days_threshold
        low_stock = [p for p in all_metrics if p["days_of_stock"] is not None and 0 < p["days_of_stock"] <= threshold]
        recs = [r for r in all_recs if r["alert_type"] == "LOW_STOCK"]
        
        evidence = {
            "source": "inventory + sales (last 7 days)",
            "period": f"Ending {latest_date}",
            "calculation": f"current_stock / avg_daily_sales_7d <= {threshold} days",
            "parameters": {"threshold_days": threshold}
        }
        data_used = {
            "query_type": "Low Stock Risk Audit",
            "matching_products_count": len(low_stock),
            "threshold_applied": f"<= {threshold} days",
            "products": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "avg_daily_sales": p["effective_daily_sales"],
                    "days_of_stock": p["days_of_stock"],
                    "reorder_units_recommended": p["reorder_units_recommended"]
                }
                for p in low_stock
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "evidence": evidence,
            "items": low_stock,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 2. RUN OUT NEXT WEEK
    elif intent == "RUN_OUT_NEXT_WEEK":
        week_limit = 7.0
        runout_items = [p for p in all_metrics if p["days_of_stock"] is not None and 0 < p["days_of_stock"] <= week_limit]
        recs = [r for r in all_recs if r["product_id"] in [p["product_id"] for p in runout_items]]
        
        evidence = {
            "source": "inventory + sales run-rate",
            "period": f"7-day lookback ending {latest_date}",
            "calculation": "current_stock / avg_daily_sales_7d <= 7.0 days",
            "parameters": {"projection_window": "7 days"}
        }
        data_used = {
            "query_type": "Forward 7-Day Stockout Projection",
            "products_at_risk": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "avg_daily_sales": p["effective_daily_sales"],
                    "days_remaining": p["days_of_stock"]
                }
                for p in runout_items
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "evidence": evidence,
            "items": runout_items,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 3. OVERSTOCK
    elif intent == "OVERSTOCK":
        overstocked = [p for p in all_metrics if p["status"] == "OVERSTOCK"]
        recs = [r for r in all_recs if r["alert_type"] == "OVERSTOCK"]
        evidence = {
            "source": "inventory + sales (30-day baseline)",
            "period": f"30-day window ending {latest_date}",
            "calculation": f"days_of_stock > {cfg.overstock_days_threshold} days and current_stock >= {cfg.slow_moving_min_stock}",
            "parameters": {"overstock_threshold_days": cfg.overstock_days_threshold}
        }
        data_used = {
            "query_type": "Excess Inventory Audit",
            "matching_products_count": len(overstocked),
            "products": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "avg_daily_sales_30d": p["avg_daily_sales_30d"],
                    "days_of_stock": p["days_of_stock"]
                }
                for p in overstocked
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "evidence": evidence,
            "items": overstocked,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 4. SLOW MOVING
    elif intent == "SLOW_MOVING":
        slow = [p for p in all_metrics if p["status"] == "SLOW_MOVING"]
        recs = [r for r in all_recs if r["alert_type"] == "SLOW_MOVING"]
        evidence = {
            "source": "sales (30d) + inventory",
            "period": f"30-day window ending {latest_date}",
            "calculation": f"velocity <= {cfg.slow_moving_daily_sales} units/day and current_stock >= {cfg.slow_moving_min_stock}",
            "parameters": {"max_velocity": cfg.slow_moving_daily_sales}
        }
        data_used = {
            "query_type": "Slow-Moving Stagnant Stock Audit",
            "matching_products_count": len(slow),
            "products": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "units_sold_30d": p["units_sold_30d"],
                    "avg_daily_sales": p["avg_daily_sales_30d"]
                }
                for p in slow
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "evidence": evidence,
            "items": slow,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 5. TOP SELLER
    elif intent == "TOP_SELLER":
        top = get_top_selling_products(limit=5, store_id=target_store_id)
        evidence = {
            "source": "sales (30-day aggregate)",
            "period": f"30 days ending {latest_date}",
            "calculation": "ORDER BY total_revenue DESC LIMIT 5",
            "parameters": {"limit": 5}
        }
        data_used = {
            "query_type": "Top Revenue Generating Products",
            "top_products": top
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "evidence": evidence,
            "items": top,
            "recommendations": [],
            "insufficient_data": False
        }

    # 6. WHY SALES DECREASED (Difficult Demo Test Case)
    elif intent == "WHY_SALES_DECREASED":
        target = product if product else next((p for p in all_metrics if p["status"] == "SALES_DROP"), None)
        if target:
            pid = target["product_id"]
            p_data = next((p for p in all_metrics if p["product_id"] == pid), None)
            comp = compare_sales_periods(window_days=7, store_id=target_store_id, product_id=pid)
            
            evidence = {
                "source": "sales transactions",
                "period": f"Current 7d ({comp['current_period']}) vs Previous 7d ({comp['previous_period']})",
                "product_id": pid,
                "calculation": "((current_units - previous_units) / previous_units) * 100",
                "parameters": {"window_days": 7}
            }
            data_used = {
                "query_type": "Causal Analysis of Sales Contraction",
                "product_analyzed": p_data["product_name"] if p_data else target.get("product_name"),
                "current_7d_units": comp["current_units"],
                "previous_7d_units": comp["previous_units"],
                "change_percent": comp["units_change_percent"],
                "internal_data_logged": ["daily_quantity_sold", "daily_revenue", "inventory_balance"],
                "external_data_untracked": ["competitor_pricing", "footfall_count", "marketing_spend", "customer_reviews"]
            }
            rec = {
                "finding": f"Sales for {p_data['product_name']} declined by {abs(comp['units_change_percent'])}% over the last 7 days.",
                "supporting_numbers": {
                    "current_stock": p_data["current_stock"],
                    "recent_avg_daily_sales": p_data["avg_daily_sales_7d"],
                    "historical_avg_daily_sales": p_data["avg_daily_sales_30d"],
                    "sales_change_pct": comp["units_change_percent"]
                },
                "assumption": "Available store data records transaction quantities but does not record external competitor promotions, distributor shortages, or footfall shifts.",
                "recommended_action": "Check shelf visibility and expiration dates; survey competitor pricing; review pricing/promotion options.",
                "alert_type": "SALES_DROP",
                "severity": "WARNING",
                "product_id": pid,
                "product_name": p_data["product_name"]
            }
            return {
                "intent": intent,
                "data_used": data_used,
                "evidence": evidence,
                "product_data": p_data,
                "insufficient_data": True,  # Cannot establish root cause without guessing
                "recommendations": [rec]
            }
        else:
            return {
                "intent": intent,
                "data_used": {"query_type": "Causal Analysis", "error": "No product specified"},
                "evidence": {"source": "sales", "calculation": "none"},
                "insufficient_data": True,
                "recommendations": []
            }

    # 7. PRODUCT PERFORMANCE
    elif intent == "PRODUCT_PERFORMANCE":
        if product:
            pid = product["product_id"]
            p_data = next((p for p in all_metrics if p["product_id"] == pid), None)
            if p_data:
                evidence = {
                    "source": "products + inventory + sales (30d)",
                    "period": f"30 days ending {latest_date}",
                    "product_id": pid,
                    "calculation": "units_sold, revenue, and days_of_stock = current_stock / avg_daily_sales"
                }
                data_used = {
                    "query_type": f"Single SKU Performance: {p_data['product_name']}",
                    "product_id": pid,
                    "price": p_data["price"],
                    "current_stock": p_data["current_stock"],
                    "units_sold_30d": p_data["units_sold_30d"],
                    "revenue_30d": p_data["revenue_30d"],
                    "avg_daily_sales_7d": p_data["avg_daily_sales_7d"],
                    "days_of_stock": p_data["days_of_stock"],
                    "status": p_data["status"]
                }
                recs = [r for r in all_recs if r["product_id"] == pid]
                return {
                    "intent": intent,
                    "data_used": data_used,
                    "evidence": evidence,
                    "product_data": p_data,
                    "recommendations": recs,
                    "insufficient_data": False
                }

        return {
            "intent": intent,
            "data_used": {"query_type": "Product Catalogue Lookup", "status": "Not Found"},
            "evidence": {"source": "products", "calculation": "exact match"},
            "insufficient_data": True,
            "recommendations": []
        }

    # 8. ATTENTION TODAY
    elif intent == "ATTENTION_TODAY":
        urgent = [r for r in all_recs if r["severity"] in ("URGENT", "WARNING")][:4]
        summary = get_total_sales_summary(days=1, store_id=target_store_id)
        evidence = {
            "source": "inventory rules + daily alerts",
            "period": f"Latest date {latest_date}",
            "calculation": "evaluate all products against configured thresholds"
        }
        data_used = {
            "query_type": "Daily Operational Priority Audit",
            "active_alerts_total": len(all_recs),
            "urgent_recommendations": [
                {"finding": r["finding"], "action": r["recommended_action"]} for r in urgent
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "evidence": evidence,
            "recommendations": urgent,
            "insufficient_data": False
        }

    # Default General
    evidence = {
        "source": "retail_copilot catalogue",
        "period": f"Current snapshot {latest_date}",
        "calculation": "overview"
    }
    return {
        "intent": "GENERAL",
        "data_used": {"query_type": "Catalogue Overview", "total_products": len(all_metrics)},
        "evidence": evidence,
        "recommendations": all_recs[:2],
        "insufficient_data": False
    }

def format_deterministic_answer(question: str, pipeline_result: Dict[str, Any]) -> str:
    """Fallback natural-language synthesis when Gemini API is offline or unconfigured."""
    intent = pipeline_result["intent"]
    items = pipeline_result.get("items", [])

    if intent == "LOW_STOCK":
        if not items:
            return "All products currently maintain healthy inventory buffers above the configured threshold."
        lines = [f"Found **{len(items)} products** at risk of running out:"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: Stock: **{p['current_stock']} units** | Run rate: **{p['effective_daily_sales']} units/day** | Remaining supply: **{p['days_of_stock']} days**.")
        lines.append("\n**Recommended Action**: Issue purchase orders to restore safety buffers before stock-out occurs.")
        return "\n".join(lines)

    elif intent == "RUN_OUT_NEXT_WEEK":
        if not items:
            return "Based on 7-day velocity calculations, no products are projected to run out in the next 7 days."
        lines = [f"Based on current sales velocity, **{len(items)} products** are projected to deplete within next week (7 days):"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: **{p['current_stock']} units** remaining. At **{p['effective_daily_sales']} units/day**, stock will deplete in **{p['days_of_stock']} days**.")
        lines.append("\n*Assumption: Demand velocity remains constant and no supplier shipments arrive during this window.*")
        return "\n".join(lines)

    elif intent == "OVERSTOCK":
        if not items:
            return "No products currently exceed the overstock threshold."
        lines = [f"Identified **{len(items)} overstocked products** holding excess inventory:"]
        for p in items:
            days_str = f"{p['days_of_stock']} days" if p['days_of_stock'] else "> 300 days"
            lines.append(f"• **{p['product_name']}**: Holding **{p['current_stock']} units** against **{p['avg_daily_sales_30d']} units/day** sales velocity (~{days_str} of supply).")
        lines.append("\n**Recommended Action**: Halt new purchase orders and initiate a bundled promotional discount to release working capital.")
        return "\n".join(lines)

    elif intent == "SLOW_MOVING":
        if not items:
            return "No stagnant inventory detected. All catalogued items are moving at acceptable velocity."
        lines = [f"Found **{len(items)} slow-moving products** with high idle inventory:"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: Sold only **{p['units_sold_30d']} units** in past 30 days while holding **{p['current_stock']} units** in stock.")
        lines.append("\n**Recommended Action**: Review retail pricing, offer promotional discounts, or relocate to higher footfall shelf space.")
        return "\n".join(lines)

    elif intent == "TOP_SELLER":
        if not items:
            return "No sales transactions recorded in the past 30 days."
        top = items[0]
        lines = [
            f"The best-selling product this month is **{top['product_name']}**.",
            f"• **Total Revenue**: ₹{top['total_revenue']:,.2f}",
            f"• **Units Sold**: {top['total_units']} units",
            f"• **Category**: {top['category']}"
        ]
        if len(items) > 1:
            lines.append("\n**Other Top Performers:**")
            for other in items[1:4]:
                lines.append(f"• {other['product_name']}: ₹{other['total_revenue']:,.2f} ({other['total_units']} units)")
        return "\n".join(lines)

    elif intent == "WHY_SALES_DECREASED":
        p = pipeline_result.get("product_data")
        if not p:
            return "I don't have enough data to identify a sales decrease without a specified product."
        data = pipeline_result["data_used"]
        return (
            f"The available transaction data confirms a sales drop for **{p['product_name']}**: sales fell by **{data['change_percent']}%** "
            f"(from {data['previous_7d_units']} to {data['current_7d_units']} units).\n\n"
            f"However, **the available data does not contain enough information to determine why** sales dropped. "
            f"Transaction logs record sales quantities and revenue, but do not contain external data such as competitor discounts, footfall shifts, or supplier delays.\n\n"
            f"**Recommended Grounded Actions**: Check shelf visibility, verify product expiry, survey competitor prices, and confirm stock presentation."
        )

    elif intent == "PRODUCT_PERFORMANCE":
        p = pipeline_result.get("product_data")
        if not p:
            return "I don't have enough data on that product. It does not appear in our store catalogue. Please check the spelling or view the Inventory Matrix."
        days_str = f"{p['days_of_stock']} days" if p['days_of_stock'] else "N/A"
        return (
            f"**Performance Summary for {p['product_name']}**:\n"
            f"• **Category**: {p['category']} | **Price**: ₹{p['price']:.2f}\n"
            f"• **Current Stock**: {p['current_stock']} units\n"
            f"• **30-Day Sales**: {p['units_sold_30d']} units (Revenue: ₹{p['revenue_30d']:,.2f})\n"
            f"• **Recent 7-Day Velocity**: {p['avg_daily_sales_7d']} units/day\n"
            f"• **Estimated Days of Supply**: {days_str}\n"
            f"• **Health Status**: {p['status']}"
        )

    elif intent == "ATTENTION_TODAY":
        recs = pipeline_result.get("recommendations", [])
        lines = [
            f"**Daily Operational Summary**:\n"
            f"Identified **{len(recs)} critical items** requiring management attention today:\n"
        ]
        for idx, r in enumerate(recs[:4], 1):
            lines.append(f"{idx}. **{r['product_name']}** ({r['severity']}): {r['recommended_action']}")
        return "\n".join(lines)

    return "I can answer questions regarding stock-outs, overstocked products, sales velocity, top sellers, and stock health. Try asking: *'What products are running out?'* or *'What needs attention today?'*"

def handle_chat_query(question: str, store_id: Optional[str] = None) -> ChatResponse:
    """
    Main Copilot entrypoint:
    1. Extracts intent and entities
    2. Runs deterministic Python services
    3. Synthesizes response via Gemini if available; falls back to deterministic engine
    4. Attaches structured EvidenceObject and recommendations
    """
    intent_data = identify_intent(question)
    pipeline_result = execute_deterministic_pipeline(intent_data, store_id=store_id)

    insufficient = pipeline_result.get("insufficient_data", False)
    recommendations = [Recommendation(**r) for r in pipeline_result.get("recommendations", [])]
    data_used = pipeline_result.get("data_used", {})
    evidence_dict = pipeline_result.get("evidence", {})
    evidence_obj = EvidenceObject(**evidence_dict) if evidence_dict else None

    # If data is insufficient or causal inquiry beyond database, enforce strict deterministic honesty
    answer_text = None
    source = "deterministic_python_engine"
    if insufficient:
        answer_text = format_deterministic_answer(question, pipeline_result)
        source = "deterministic_python_engine"
    elif is_gemini_available():
        gemini_answer = generate_grounded_response(
            question=question,
            calculation_data=pipeline_result["data_used"],
            evidence=evidence_dict
        )
        if gemini_answer:
            answer_text = gemini_answer
            source = "gemini_grounded_ai"

    # Fallback to deterministic template engine if Gemini offline
    if not answer_text:
        answer_text = format_deterministic_answer(question, pipeline_result)

    return ChatResponse(
        question=question,
        answer=answer_text,
        data_used=data_used,
        recommendations=recommendations,
        insufficient_data=insufficient,
        source=source,
        evidence=evidence_obj
    )
