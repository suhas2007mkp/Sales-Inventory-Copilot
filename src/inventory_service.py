"""
Inventory Service for Sales & Inventory Copilot (PS03)
Provides deterministic inventory analytics:
- Stock velocity (run-rate) & days-of-stock
- Stock-out forecasting (days_remaining = current_stock / avg_daily_sales)
- Overstock detection & working capital blockage
- Slow-moving inventory identification
- Reorder quantity recommendations & inventory turnover
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from src.database import get_connection, get_latest_date
from src.utils import safe_divide, calc_pct_change, get_date_range
from src.rules import get_active_config, InventoryConfig

def get_product_inventory_metrics(
    store_id: Optional[str] = None,
    config: Optional[InventoryConfig] = None
) -> List[Dict[str, Any]]:
    """
    Computes deterministic inventory velocity and metrics for all products.
    Uses pure indexed SQL queries for fast execution.
    """
    cfg = config or get_active_config()
    latest_date = get_latest_date()
    start_7d, _ = get_date_range(latest_date, cfg.recent_period_days)
    start_30d, _ = get_date_range(latest_date, cfg.historical_period_days)

    conn = get_connection()
    cursor = conn.cursor()

    # Query latest inventory per product
    inv_query = """
    SELECT product_id, SUM(stock_quantity) as total_stock
    FROM inventory
    WHERE date = (SELECT MAX(date) FROM inventory)
    """
    params_inv = []
    if store_id:
        inv_query += " AND store_id = ?"
        params_inv.append(store_id)
    inv_query += " GROUP BY product_id;"
    cursor.execute(inv_query, params_inv)
    inv_map = {row["product_id"]: int(row["total_stock"]) for row in cursor.fetchall()}

    # Query 30-day sales per product
    sales_30d_query = """
    SELECT product_id, 
           SUM(quantity_sold) as units_30d, 
           ROUND(SUM(revenue), 2) as revenue_30d
    FROM sales
    WHERE date >= ? AND date <= ?
    """
    params_30d = [start_30d, latest_date]
    if store_id:
        sales_30d_query += " AND store_id = ?"
        params_30d.append(store_id)
    sales_30d_query += " GROUP BY product_id;"
    cursor.execute(sales_30d_query, params_30d)
    sales_30d_map = {row["product_id"]: (int(row["units_30d"]), float(row["revenue_30d"])) for row in cursor.fetchall()}

    # Query 7-day sales per product
    sales_7d_query = """
    SELECT product_id, 
           SUM(quantity_sold) as units_7d, 
           ROUND(SUM(revenue), 2) as revenue_7d
    FROM sales
    WHERE date >= ? AND date <= ?
    """
    params_7d = [start_7d, latest_date]
    if store_id:
        sales_7d_query += " AND store_id = ?"
        params_7d.append(store_id)
    sales_7d_query += " GROUP BY product_id;"
    cursor.execute(sales_7d_query, params_7d)
    sales_7d_map = {row["product_id"]: (int(row["units_7d"]), float(row["revenue_7d"])) for row in cursor.fetchall()}

    # Fetch all products
    cursor.execute("SELECT product_id, product_name, category, price, supplier FROM products ORDER BY product_id ASC;")
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()

    metrics = []
    for p in products:
        pid = p["product_id"]
        stock = inv_map.get(pid, 0)
        units_30d, rev_30d = sales_30d_map.get(pid, (0, 0.0))
        units_7d, rev_7d = sales_7d_map.get(pid, (0, 0.0))

        avg_daily_30d = round(safe_divide(units_30d, 30.0), 2)
        avg_daily_7d = round(safe_divide(units_7d, 7.0), 2)

        effective_daily = avg_daily_7d if avg_daily_7d > 0 else avg_daily_30d

        # Days of Stock calculation
        if effective_daily > 0:
            days_of_stock = round(safe_divide(stock, effective_daily), 1)
        else:
            days_of_stock = 999.0 if stock > 0 else 0.0

        # Change %
        sales_change_pct = calc_pct_change(avg_daily_7d, avg_daily_30d)

        # Inventory Turnover (30-day run rate / current stock)
        turnover_ratio = round(safe_divide(units_30d, stock), 2) if stock > 0 else 0.0

        # Recommended Reorder (buffer for 21 days of safety stock)
        target_buffer_units = int(round(effective_daily * 21))
        reorder_qty = max(0, target_buffer_units - stock)

        # Health Classification
        status = "HEALTHY"
        if stock > 0 and days_of_stock < cfg.low_stock_days_threshold:
            status = "LOW_STOCK"
        elif days_of_stock > cfg.overstock_days_threshold and stock >= cfg.slow_moving_min_stock:
            status = "OVERSTOCK"
        elif stock >= cfg.slow_moving_min_stock and avg_daily_30d <= cfg.slow_moving_daily_sales:
            status = "SLOW_MOVING"
        elif avg_daily_30d >= 0.3 and safe_divide(avg_daily_7d, avg_daily_30d) >= cfg.spike_ratio_threshold:
            status = "SALES_SPIKE"
        elif avg_daily_30d >= 0.5 and safe_divide(avg_daily_7d, avg_daily_30d) <= cfg.drop_ratio_threshold:
            status = "SALES_DROP"

        metrics.append({
            "product_id": pid,
            "product_name": p["product_name"],
            "category": p["category"],
            "price": float(p["price"]),
            "supplier": p["supplier"],
            "current_stock": stock,
            "units_sold_30d": units_30d,
            "revenue_30d": rev_30d,
            "avg_daily_sales_30d": avg_daily_30d,
            "units_sold_7d": units_7d,
            "revenue_7d": rev_7d,
            "avg_daily_sales_7d": avg_daily_7d,
            "effective_daily_sales": effective_daily,
            "days_of_stock": days_of_stock if days_of_stock < 999 else None,
            "days_of_stock_display": f"{days_of_stock:.1f}" if days_of_stock < 999 else "> 300 (Idle)",
            "sales_change_pct": sales_change_pct,
            "turnover_ratio": turnover_ratio,
            "reorder_units_recommended": reorder_qty,
            "status": status
        })

    return metrics

def get_stockout_predictions(
    threshold_days: Optional[float] = None,
    store_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns products at risk of stock-out with deterministic run-rate calculations.
    """
    cfg = get_active_config()
    limit_days = threshold_days if threshold_days is not None else cfg.low_stock_days_threshold
    all_metrics = get_product_inventory_metrics(store_id=store_id, config=cfg)

    at_risk = []
    for p in all_metrics:
        dos = p["days_of_stock"]
        if dos is not None and 0 < dos <= limit_days:
            at_risk.append({
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "category": p["category"],
                "current_stock": p["current_stock"],
                "average_daily_sales": p["effective_daily_sales"],
                "days_remaining": dos,
                "threshold_applied": limit_days,
                "calculation": f"current_stock ({p['current_stock']}) / avg_daily_sales ({p['effective_daily_sales']}) = {dos} days",
                "status": "critical" if dos <= cfg.critical_stock_days_threshold else "warning",
                "recommended_reorder_units": p["reorder_units_recommended"]
            })

    at_risk.sort(key=lambda x: x["days_remaining"])
    return at_risk

def get_inventory_overview(store_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculates aggregate inventory valuation and stock health distribution."""
    metrics = get_product_inventory_metrics(store_id=store_id)
    total_units = sum(p["current_stock"] for p in metrics)
    total_value = round(sum(p["current_stock"] * p["price"] for p in metrics), 2)

    status_counts = {}
    for p in metrics:
        st = p["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "total_stock_units": total_units,
        "total_inventory_value_inr": total_value,
        "product_count": len(metrics),
        "health_distribution": status_counts
    }
