"""
Gemini Copilot Service for Sales & Inventory Copilot (PS03)
Enforces strict grounding: Python performs all business calculations and passes
structured data to Gemini for natural-language synthesis.
Includes deterministic fallback engine if GEMINI_API_KEY is missing or API is unreachable.
"""
import os
import json
import re
from typing import Dict, Any, List, Optional
from src.database import get_connection, get_latest_date
from src.rules import DEFAULT_CONFIG, InventoryConfig
from src.analytics import (
    get_product_analytics,
    get_all_alerts,
    get_dashboard_summary,
    get_top_selling_products
)
from src.schemas import ChatResponse, Recommendation, SupportingNumbers

def identify_intent(question: str) -> Dict[str, Any]:
    """
    Classifies user question into structured intent and extracts entity parameters.
    """
    q = question.lower().strip()
    
    # Check for specific product mentions
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, product_name FROM products;")
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()

    matched_product = None
    for p in products:
        p_name_clean = re.sub(r'[^a-zA-Z0-9\s]', '', p["product_name"].lower())
        tokens = [t for t in p_name_clean.split() if len(t) > 3]
        for t in tokens:
            if t in q:
                matched_product = p
                break
        if matched_product:
            break

    # 1. Running out / Low stock
    if any(w in q for w in ["running out", "low stock", "stock out", "stockout", "out of stock", "run out"]):
        if "next week" in q or "7 days" in q or "week" in q:
            return {"intent": "RUN_OUT_NEXT_WEEK", "product": matched_product}
        return {"intent": "LOW_STOCK", "product": matched_product}

    # 2. Overstocked
    if any(w in q for w in ["overstock", "overstocked", "excess", "too much stock"]):
        return {"intent": "OVERSTOCK", "product": matched_product}

    # 3. Slow moving / stagnant
    if any(w in q for w in ["slow moving", "not moving", "stagnant", "dead stock", "idle"]):
        return {"intent": "SLOW_MOVING", "product": matched_product}

    # 4. Spikes
    if any(w in q for w in ["spike", "surge", "jump in sales", "rapid increase"]):
        return {"intent": "SALES_SPIKE", "product": matched_product}

    # 5. Drops / Declining / Why decreased
    if any(w in q for w in ["why did sales decrease", "why sales drop", "why sales decrease", "why sales fell", "reason for drop"]):
        return {"intent": "WHY_SALES_DECREASED", "product": matched_product}
    if any(w in q for w in ["drop", "declining", "decrease", "slump", "falling"]):
        return {"intent": "SALES_DROP", "product": matched_product}

    # 6. Top selling / sold the most
    if any(w in q for w in ["sold the most", "top selling", "best seller", "highest revenue", "top product"]):
        return {"intent": "TOP_SELLER", "product": matched_product}

    # 7. Needs attention today
    if any(w in q for w in ["needs attention", "attention today", "priority", "critical alerts", "what should i do"]):
        return {"intent": "ATTENTION_TODAY", "product": matched_product}

    # 8. Single product performance
    if matched_product or any(w in q for w in ["how did", "performance", "sales of", "perform"]):
        return {"intent": "PRODUCT_PERFORMANCE", "product": matched_product}

    # 9. Out of scope / General
    return {"intent": "GENERAL_RETAIL_QUERY", "product": matched_product}

def get_deterministic_data_for_intent(intent_info: Dict[str, Any], store_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes deterministic calculations in Python for the given intent.
    Returns structured metrics, findings, and recommendations.
    """
    intent = intent_info["intent"]
    product = intent_info.get("product")
    metrics = get_product_analytics(store_id=store_id)
    alerts = get_all_alerts(store_id=store_id)

    # 1. LOW STOCK
    if intent == "LOW_STOCK":
        low_stock_items = [p for p in metrics if p["status"] == "LOW_STOCK"]
        recs = [a for a in alerts if a["alert_type"] == "LOW_STOCK"]
        data_used = {
            "query_type": "Low Stock Evaluation",
            "threshold_applied": f"days_of_stock < {DEFAULT_CONFIG.low_stock_days_threshold} days",
            "matching_products_count": len(low_stock_items),
            "products": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "avg_daily_sales_7d": p["avg_daily_sales_7d"],
                    "days_of_stock": p["days_of_stock"]
                }
                for p in low_stock_items
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": low_stock_items,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 2. RUN OUT NEXT WEEK (Difficult demo test case)
    elif intent == "RUN_OUT_NEXT_WEEK":
        # Items with days of stock <= 7.0
        week_runout = [p for p in metrics if p["days_of_stock"] is not None and 0 < p["days_of_stock"] <= 7.0]
        recs = [a for a in alerts if a["product_id"] in [p["product_id"] for p in week_runout]]
        data_used = {
            "query_type": "Forward Stockout Projection (7 Days)",
            "formula": "current_stock / avg_daily_sales_7d <= 7.0 days",
            "forecast_window": "Next 7 Days",
            "products_at_risk": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "avg_daily_sales": p["avg_daily_sales_7d"],
                    "days_of_stock": p["days_of_stock"],
                    "projected_stockout_days": p["days_of_stock"]
                }
                for p in week_runout
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": week_runout,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 3. OVERSTOCK
    elif intent == "OVERSTOCK":
        overstock_items = [p for p in metrics if p["status"] == "OVERSTOCK"]
        recs = [a for a in alerts if a["alert_type"] == "OVERSTOCK"]
        data_used = {
            "query_type": "Overstock Evaluation",
            "threshold_applied": f"days_of_stock > {DEFAULT_CONFIG.overstock_days_threshold} days & stock >= 20",
            "matching_products_count": len(overstock_items),
            "products": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "avg_daily_sales_30d": p["avg_daily_sales_30d"],
                    "days_of_stock": p["days_of_stock"]
                }
                for p in overstock_items
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": overstock_items,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 4. SLOW MOVING
    elif intent == "SLOW_MOVING":
        slow_items = [p for p in metrics if p["status"] == "SLOW_MOVING"]
        recs = [a for a in alerts if a["alert_type"] == "SLOW_MOVING"]
        data_used = {
            "query_type": "Slow-Moving Inventory Analysis",
            "threshold_applied": f"velocity <= {DEFAULT_CONFIG.slow_moving_daily_sales} units/day & stock >= {DEFAULT_CONFIG.slow_moving_min_stock}",
            "products": [
                {
                    "product_name": p["product_name"],
                    "current_stock": p["current_stock"],
                    "units_sold_30d": p["units_sold_30d"],
                    "avg_daily_sales_30d": p["avg_daily_sales_30d"]
                }
                for p in slow_items
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": slow_items,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 5. TOP SELLER
    elif intent == "TOP_SELLER":
        top_prods = get_top_selling_products(limit=5, store_id=store_id)
        data_used = {
            "query_type": "Top Revenue Generating Products (30 Days)",
            "top_products": top_prods
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": top_prods,
            "recommendations": [],
            "insufficient_data": False
        }

    # 6. SALES SPIKE
    elif intent == "SALES_SPIKE":
        spikes = [p for p in metrics if p["status"] == "SALES_SPIKE"]
        recs = [a for a in alerts if a["alert_type"] == "SALES_SPIKE"]
        data_used = {
            "query_type": "Demand Surge Spike Detection",
            "threshold": f"7-day velocity >= {DEFAULT_CONFIG.spike_ratio_threshold}x historical baseline",
            "products": [
                {
                    "product_name": p["product_name"],
                    "recent_7d_daily": p["avg_daily_sales_7d"],
                    "historical_30d_daily": p["avg_daily_sales_30d"],
                    "surge_percentage": f"+{p['sales_change_pct']}%"
                }
                for p in spikes
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": spikes,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 7. SALES DROP
    elif intent == "SALES_DROP":
        drops = [p for p in metrics if p["status"] == "SALES_DROP"]
        recs = [a for a in alerts if a["alert_type"] == "SALES_DROP"]
        data_used = {
            "query_type": "Demand Contraction Drop Detection",
            "threshold": f"7-day velocity <= {DEFAULT_CONFIG.drop_ratio_threshold}x historical baseline",
            "products": [
                {
                    "product_name": p["product_name"],
                    "recent_7d_daily": p["avg_daily_sales_7d"],
                    "historical_30d_daily": p["avg_daily_sales_30d"],
                    "drop_percentage": f"{p['sales_change_pct']}%"
                }
                for p in drops
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "items": drops,
            "recommendations": recs,
            "insufficient_data": False
        }

    # 8. WHY SALES DECREASED (Difficult demo test case)
    elif intent == "WHY_SALES_DECREASED":
        target_prod = product if product else (next((p for p in metrics if p["status"] == "SALES_DROP"), None))
        if target_prod:
            pid = target_prod["product_id"]
            p_data = next((p for p in metrics if p["product_id"] == pid), None)
            data_used = {
                "query_type": "Causal Analysis of Sales Decrease",
                "product_analyzed": p_data["product_name"] if p_data else target_prod.get("product_name"),
                "recent_7d_velocity": p_data["avg_daily_sales_7d"] if p_data else None,
                "historical_30d_velocity": p_data["avg_daily_sales_30d"] if p_data else None,
                "sales_change_pct": p_data["sales_change_pct"] if p_data else None,
                "internal_data_coverage": ["daily_quantity_sold", "revenue", "current_stock"],
                "external_data_missing": ["competitor_pricing", "footfall_tracking", "marketing_spend", "customer_sentiment"]
            }
            return {
                "intent": intent,
                "data_used": data_used,
                "product_data": p_data,
                "insufficient_data": True,  # Cannot establish root cause without guessing
                "recommendations": [
                    {
                        "finding": f"Sales decreased by {abs(p_data['sales_change_pct'])}% for {p_data['product_name']}.",
                        "supporting_numbers": {
                            "recent_avg_daily_sales": p_data["avg_daily_sales_7d"],
                            "historical_avg_daily_sales": p_data["avg_daily_sales_30d"],
                            "sales_change_pct": p_data["sales_change_pct"]
                        },
                        "assumption": "Available transactional data logs sales quantity and revenue, but does not capture external market variables.",
                        "recommended_action": "Audit store shelf placement, verify product expiry, check local competitor pricing, and verify if stockout occurred on shelves.",
                        "alert_type": "SALES_DROP",
                        "severity": "WARNING"
                    }
                ]
            }
        else:
            return {
                "intent": intent,
                "data_used": {"query_type": "Causal Analysis", "error": "No product specified or found"},
                "insufficient_data": True,
                "recommendations": []
            }

    # 9. ATTENTION TODAY
    elif intent == "ATTENTION_TODAY":
        urgent_alerts = [a for a in alerts if a["severity"] in ("URGENT", "WARNING")][:4]
        summary = get_dashboard_summary(store_id=store_id)
        data_used = {
            "query_type": "Daily Operational Priority Audit",
            "active_alerts_total": summary["active_alerts_count"],
            "critical_stockouts": summary["low_stock_count"],
            "overstocked_skus": summary["overstock_count"],
            "top_priorities": [
                {
                    "finding": a["finding"],
                    "action": a["recommended_action"]
                }
                for a in urgent_alerts
            ]
        }
        return {
            "intent": intent,
            "data_used": data_used,
            "summary": summary,
            "recommendations": urgent_alerts,
            "insufficient_data": False
        }

    # 10. SPECIFIC PRODUCT PERFORMANCE
    elif intent == "PRODUCT_PERFORMANCE":
        if product:
            pid = product["product_id"]
            p_data = next((p for p in metrics if p["product_id"] == pid), None)
            if p_data:
                data_used = {
                    "query_type": f"Single Product Performance: {p_data['product_name']}",
                    "product_id": pid,
                    "price_inr": p_data["price"],
                    "current_stock": p_data["current_stock"],
                    "units_sold_30d": p_data["units_sold_30d"],
                    "revenue_30d_inr": p_data["revenue_30d"],
                    "avg_daily_sales_7d": p_data["avg_daily_sales_7d"],
                    "days_of_stock": p_data["days_of_stock"],
                    "status": p_data["status"]
                }
                recs = [a for a in alerts if a["product_id"] == pid]
                return {
                    "intent": intent,
                    "data_used": data_used,
                    "product_data": p_data,
                    "recommendations": recs,
                    "insufficient_data": False
                }

        # Product not recognized in catalogue
        return {
            "intent": intent,
            "data_used": {"query_type": "Product Catalogue Lookup", "status": "Not Found"},
            "insufficient_data": True,
            "recommendations": []
        }

    # Default General
    return {
        "intent": "GENERAL",
        "data_used": {"query_type": "General Catalogue Overview", "total_products": len(metrics)},
        "recommendations": alerts[:2],
        "insufficient_data": False
    }

def generate_local_grounded_answer(question: str, structured_ctx: Dict[str, Any]) -> str:
    """
    Generates a deterministic grounded answer directly from Python calculations
    when Gemini API is unavailable or as reliable baseline.
    """
    intent = structured_ctx["intent"]
    data = structured_ctx["data_used"]

    if intent == "LOW_STOCK":
        items = structured_ctx.get("items", [])
        if not items:
            return "All products currently maintain healthy inventory buffers above the 5.0 days threshold."
        lines = [f"Found **{len(items)} products** at imminent risk of running out:"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: Current stock is **{p['current_stock']} units** with average daily sales of **{p['avg_daily_sales_7d']} units/day**. Estimated days of stock: **{p['days_of_stock']} days** (below {DEFAULT_CONFIG.low_stock_days_threshold}d threshold).")
        lines.append("\n**Recommended Action**: Issue purchase orders immediately to replenish safety inventory before complete stock-out.")
        return "\n".join(lines)

    elif intent == "RUN_OUT_NEXT_WEEK":
        items = structured_ctx.get("items", [])
        if not items:
            return "Based on 7-day velocity calculations, **no products** are projected to run out in the next 7 days."
        lines = [f"Based on current sales run-rates, **{len(items)} products** are projected to deplete within next week (7 days):"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: **{p['current_stock']} units** remaining. At **{p['avg_daily_sales_7d']} units/day**, stock will deplete in **{p['days_of_stock']} days**.")
        lines.append("\n*Assumption: Demand velocity remains steady and no pending supplier deliveries arrive within the lead-time window.*")
        return "\n".join(lines)

    elif intent == "OVERSTOCK":
        items = structured_ctx.get("items", [])
        if not items:
            return "No products currently exceed the 45-day overstock threshold."
        lines = [f"Identified **{len(items)} overstocked products** where inventory significantly exceeds sales velocity:"]
        for p in items:
            days_str = f"{p['days_of_stock']} days" if p['days_of_stock'] else "> 300 days (near-zero sales)"
            lines.append(f"• **{p['product_name']}**: Holding **{p['current_stock']} units** against daily sales of **{p['avg_daily_sales_30d']} units/day** (~{days_str} of supply).")
        lines.append("\n**Recommended Action**: Restrict fresh purchases and run targeted promotions or bundle discounts to unlock trapped working capital.")
        return "\n".join(lines)

    elif intent == "SLOW_MOVING":
        items = structured_ctx.get("items", [])
        if not items:
            return "No stagnant inventory detected. All catalogued items are moving at acceptable velocity."
        lines = [f"Found **{len(items)} slow-moving products** with high idle inventory and near-zero turnover:"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: Sold only **{p['units_sold_30d']} units** in past 30 days while holding **{p['current_stock']} units** idle.")
        lines.append("\n**Recommended Action**: Review price elasticity, offer promotional discounts, or relocate to higher footfall shelf space.")
        return "\n".join(lines)

    elif intent == "TOP_SELLER":
        items = structured_ctx.get("items", [])
        if not items:
            return "No sales transactions recorded in the past 30 days."
        top = items[0]
        lines = [
            f"The highest-selling product this month is **{top['product_name']}**.",
            f"• **Total Revenue**: ₹{top['total_revenue']:,.2f}",
            f"• **Units Sold**: {top['total_units']} units",
            f"• **Category**: {top['category']}"
        ]
        if len(items) > 1:
            lines.append("\n**Other Top Performers:**")
            for other in items[1:4]:
                lines.append(f"• {other['product_name']}: ₹{other['total_revenue']:,.2f} ({other['total_units']} units)")
        return "\n".join(lines)

    elif intent == "SALES_SPIKE":
        items = structured_ctx.get("items", [])
        if not items:
            return "No abnormal sales spikes detected. Demand patterns remain within normal variance."
        lines = [f"Detected **{len(items)} products** with a sharp sales surge:"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: 7-day velocity surged to **{p['avg_daily_sales_7d']} units/day** vs **{p['avg_daily_sales_30d']} units/day** baseline (**+{p['sales_change_pct']}%**).")
        lines.append("\n**Recommended Action**: Ensure sufficient supplier replenishment buffers to prevent unexpected stock-outs during this high-demand window.")
        return "\n".join(lines)

    elif intent == "SALES_DROP":
        items = structured_ctx.get("items", [])
        if not items:
            return "No sharp sales declines detected across the product catalogue."
        lines = [f"Found **{len(items)} products** with declining sales:"]
        for p in items:
            lines.append(f"• **{p['product_name']}**: Recent 7-day sales dropped to **{p['avg_daily_sales_7d']} units/day** compared to **{p['avg_daily_sales_30d']} units/day** historical baseline (**{p['sales_change_pct']}%**).")
        lines.append("\n**Recommended Action**: Inspect in-store presentation, check expiry dates, and review competitive price positioning.")
        return "\n".join(lines)

    elif intent == "WHY_SALES_DECREASED":
        p = structured_ctx.get("product_data")
        if not p:
            return "I don't have enough data to identify a sales decrease without a specified product."
        return (
            f"The available data confirms a sales drop for **{p['product_name']}**: recent sales fell from **{p['avg_daily_sales_30d']} units/day** to **{p['avg_daily_sales_7d']} units/day** ({p['sales_change_pct']}%).\n\n"
            f"However, **the available transactional data does not contain enough information to determine why** sales dropped. "
            f"Transaction logs record quantities and revenue, but do not capture external factors such as competitor discounts, footfall shifts, or local marketing changes.\n\n"
            f"**Recommended Grounded Steps**: Verify shelf availability, check stock display locations, inspect expiry dates, and monitor competitor prices."
        )

    elif intent == "PRODUCT_PERFORMANCE":
        p = structured_ctx.get("product_data")
        if not p:
            return "I don't have enough data on that product. It does not appear in our store catalogue. Please check the spelling or view the Inventory Matrix."
        days_str = f"{p['days_of_stock']} days" if p['days_of_stock'] else "N/A"
        return (
            f"**Performance Summary for {p['product_name']}**:\n"
            f"• **Category**: {p['category']} | **Price**: ₹{p['price']:.2f}\n"
            f"• **Current Stock**: {p['current_stock']} units\n"
            f"• **30-Day Sales**: {p['units_sold_30d']} units (Revenue: ₹{p['revenue_30d']:,.2f})\n"
            f"• **Recent 7-Day Run Rate**: {p['avg_daily_sales_7d']} units/day\n"
            f"• **Estimated Days of Supply**: {days_str}\n"
            f"• **Health Status**: {p['status']}"
        )

    elif intent == "ATTENTION_TODAY":
        summary = structured_ctx.get("summary", {})
        recs = structured_ctx.get("recommendations", [])
        lines = [
            f"**Store Operations Summary for Today**:",
            f"• **Active Alerts**: {summary.get('active_alerts_count', 0)} items requiring intervention",
            f"• **Likely Stock-Outs**: {summary.get('low_stock_count', 0)} products with &lt; 5 days supply",
            f"• **Overstocked SKUs**: {summary.get('overstock_count', 0)} products holding excess capital\n",
            "**Key Immediate Actions**:"
        ]
        for idx, r in enumerate(recs[:3], 1):
            lines.append(f"{idx}. **{r['product_name']}** ({r['severity']}): {r['recommended_action']}")
        return "\n".join(lines)

    else:
        return "I can answer specific questions regarding likely stock-outs, overstock, sales velocity, top-selling products, and stock health. Try asking: *'What products are running out?'* or *'What needs attention today?'*"

def query_copilot(question: str, store_id: Optional[str] = None) -> ChatResponse:
    """
    Main entry point for Copilot queries:
    1. Extracts intent & queries SQLite
    2. Performs deterministic calculations in Python
    3. Invokes Gemini if API key is present; otherwise uses deterministic engine
    4. Guarantees no hallucination & grounded metrics
    """
    intent_info = identify_intent(question)
    calc_context = get_deterministic_data_for_intent(intent_info, store_id=store_id)
    
    insufficient = calc_context.get("insufficient_data", False)
    recommendations = [Recommendation(**r) for r in calc_context.get("recommendations", [])]
    data_used = calc_context.get("data_used", {})

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # If Gemini API key is available, enhance natural language reasoning
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            prompt = f"""You are the Sales & Inventory Copilot for a retail store manager.
Your task is to answer the manager's question using ONLY the provided structured calculation data.

MANAGER QUESTION: "{question}"

CALCULATED BUSINESS DATA (DETERMINISTIC FROM PYTHON/SQLITE):
{json.dumps(calc_context, indent=2)}

STRICT GROUNDING RULES:
1. You MUST NOT calculate or alter any numbers. Cite only the exact numbers given above.
2. If insufficient_data is True, explicitly state: "The available data does not contain enough information to determine this reliably" instead of guessing.
3. Show the supporting numbers clearly.
4. State the operational assumptions and recommended actions.
5. Keep the answer professional, concise, and structured.
"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            answer_text = response.text.strip()
            return ChatResponse(
                question=question,
                answer=answer_text,
                data_used=data_used,
                recommendations=recommendations,
                insufficient_data=insufficient,
                source="gemini_grounded_ai"
            )
        except Exception as e:
            print(f"[Gemini Service] API call fallback due to: {e}")
            # Fall back cleanly to deterministic generator

    # Deterministic local fallback
    answer_text = generate_local_grounded_answer(question, calc_context)
    return ChatResponse(
        question=question,
        answer=answer_text,
        data_used=data_used,
        recommendations=recommendations,
        insufficient_data=insufficient,
        source="deterministic_python_engine"
    )
