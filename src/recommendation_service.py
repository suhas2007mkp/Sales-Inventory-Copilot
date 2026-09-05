"""
Recommendation Service for Sales & Inventory Copilot (PS03)
Produces deterministic, actionable business recommendations based on verified data.
Zero hallucinations: evidence, calculations, and assumptions are strictly grounded in Python.
"""
from typing import List, Dict, Any, Optional
from src.inventory_service import get_product_inventory_metrics
from src.rules import (
    get_active_config,
    InventoryConfig,
    evaluate_low_stock,
    evaluate_overstock,
    evaluate_slow_moving,
    evaluate_sales_spike,
    evaluate_sales_drop
)
from src.database import get_store_by_id

def generate_recommendations(
    store_id: Optional[str] = None,
    config: Optional[InventoryConfig] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates catalogue metrics against deterministic business rules
    and generates prioritized action recommendations.
    """
    cfg = config or get_active_config()
    metrics = get_product_inventory_metrics(store_id=store_id, config=cfg)
    recommendations = []

    store_name = None
    if store_id:
        s = get_store_by_id(store_id)
        if s:
            store_name = s["store_name"]

    for p in metrics:
        pname = p["product_name"]
        pid = p["product_id"]
        stock = p["current_stock"]
        avg_7d = p["avg_daily_sales_7d"]
        avg_30d = p["avg_daily_sales_30d"]
        units_30d = p["units_sold_30d"]

        # 1. Low Stock Alert
        low_alert = evaluate_low_stock(pname, stock, avg_7d or avg_30d, cfg, store_name)
        if low_alert:
            low_alert["product_id"] = pid
            low_alert["product_name"] = pname
            low_alert["store_id"] = store_id
            low_alert["store_name"] = store_name
            recommendations.append(low_alert)
            continue  # Critical priority for this product

        # 2. Overstock Alert
        over_alert = evaluate_overstock(pname, stock, avg_30d, cfg, store_name)
        if over_alert:
            over_alert["product_id"] = pid
            over_alert["product_name"] = pname
            over_alert["store_id"] = store_id
            over_alert["store_name"] = store_name
            recommendations.append(over_alert)

        # 3. Slow Moving Alert
        slow_alert = evaluate_slow_moving(pname, stock, avg_30d, units_30d, cfg, store_name)
        if slow_alert:
            slow_alert["product_id"] = pid
            slow_alert["product_name"] = pname
            slow_alert["store_id"] = store_id
            slow_alert["store_name"] = store_name
            recommendations.append(slow_alert)

        # 4. Sales Spike Alert
        spike_alert = evaluate_sales_spike(pname, avg_7d, avg_30d, stock, cfg, store_name)
        if spike_alert:
            spike_alert["product_id"] = pid
            spike_alert["product_name"] = pname
            spike_alert["store_id"] = store_id
            spike_alert["store_name"] = store_name
            recommendations.append(spike_alert)

        # 5. Sales Drop Alert
        drop_alert = evaluate_sales_drop(pname, avg_7d, avg_30d, stock, cfg, store_name)
        if drop_alert:
            drop_alert["product_id"] = pid
            drop_alert["product_name"] = pname
            drop_alert["store_id"] = store_id
            drop_alert["store_name"] = store_name
            recommendations.append(drop_alert)

    # Sort priority: URGENT -> WARNING -> OPPORTUNITY -> INFO
    severity_order = {"URGENT": 0, "WARNING": 1, "OPPORTUNITY": 2, "INFO": 3}
    recommendations.sort(key=lambda r: severity_order.get(r.get("severity", "INFO"), 4))
    return recommendations
