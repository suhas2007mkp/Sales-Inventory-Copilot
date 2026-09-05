"""
Analytics Facade for Sales & Inventory Copilot (PS03)
Coordinates calls across specialized modular services:
- inventory_service: run rates, days of stock, stockout predictions
- sales_service: sales trends, comparisons, top/lowest products
- recommendation_service: deterministic business findings and actions
Maintains 100% backward-compatibility with existing APIs and frontend clients.
"""
from typing import Dict, Any, List, Optional
from src.inventory_service import (
    get_product_inventory_metrics,
    get_stockout_predictions,
    get_inventory_overview
)
from src.sales_service import (
    get_daily_sales_series,
    get_top_selling_products,
    get_lowest_selling_products,
    get_category_sales,
    compare_sales_periods,
    get_total_sales_summary
)
from src.recommendation_service import generate_recommendations
from src.database import get_stores, get_latest_date, get_connection
from src.rules import get_active_config, InventoryConfig

def get_product_analytics(
    store_id: Optional[str] = None,
    config: Optional[InventoryConfig] = None
) -> List[Dict[str, Any]]:
    """Delegates to inventory_service for product run-rates and days of stock."""
    return get_product_inventory_metrics(store_id=store_id, config=config)

def get_all_alerts(
    store_id: Optional[str] = None,
    config: Optional[InventoryConfig] = None
) -> List[Dict[str, Any]]:
    """Delegates to recommendation_service for prioritized action alerts."""
    return generate_recommendations(store_id=store_id, config=config)

def get_sales_trend(days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns daily time-series of revenue and quantity sold for Chart.js."""
    return get_daily_sales_series(days=days, store_id=store_id)

def get_sales_by_category(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns 30-day sales by product category."""
    return get_category_sales(days=30, store_id=store_id)

def get_dashboard_summary(store_id: Optional[str] = None) -> Dict[str, Any]:
    """Computes top-level summary metrics for dashboard KPIs."""
    latest_date = get_latest_date()
    stores = get_stores()
    
    # Query today's sales
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT COALESCE(SUM(revenue), 0.0), COALESCE(SUM(quantity_sold), 0) FROM sales WHERE date = ?"
    params = [latest_date]
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)
    cursor.execute(query, params)
    row = cursor.fetchone()
    today_rev = round(float(row[0]), 2)
    today_units = int(row[1])
    conn.close()

    metrics = get_product_inventory_metrics(store_id=store_id)
    alerts = generate_recommendations(store_id=store_id)

    low_stock = sum(1 for p in metrics if p["status"] == "LOW_STOCK")
    overstock = sum(1 for p in metrics if p["status"] == "OVERSTOCK")
    slow_moving = sum(1 for p in metrics if p["status"] == "SLOW_MOVING")
    sales_spikes = sum(1 for p in metrics if p["status"] == "SALES_SPIKE")
    sales_drops = sum(1 for p in metrics if p["status"] == "SALES_DROP")

    return {
        "total_products": len(metrics),
        "total_stores": len(stores) if not store_id else 1,
        "latest_date": latest_date,
        "today_sales_revenue": today_rev,
        "today_units_sold": today_units,
        "low_stock_count": low_stock,
        "overstock_count": overstock,
        "slow_moving_count": slow_moving,
        "sales_spikes_count": sales_spikes,
        "sales_drops_count": sales_drops,
        "active_alerts_count": len(alerts)
    }

def get_stock_levels_chart_data(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns current inventory vs safety stock levels for top products."""
    metrics = get_product_inventory_metrics(store_id=store_id)
    chart_data = []
    for p in metrics:
        safety_stock = int(round(p["effective_daily_sales"] * 7))
        chart_data.append({
            "product_id": p["product_id"],
            "product_name": p["product_name"][:18] + ("..." if len(p["product_name"]) > 18 else ""),
            "full_name": p["product_name"],
            "current_stock": p["current_stock"],
            "safety_stock": max(5, safety_stock),
            "status": p["status"],
            "days_of_stock": p["days_of_stock"]
        })
    return chart_data
