"""
Sales Service for Sales & Inventory Copilot (PS03)
Provides advanced deterministic sales analytics:
- Period aggregations (daily, weekly, monthly, 30-day)
- Period-over-period comparisons (current 7d vs previous 7d)
- Product, Store, and Category breakdowns
- Top-selling and lowest-selling products
- Sales spike and contraction anomalies
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from src.database import get_connection, get_latest_date
from src.utils import safe_divide, calc_pct_change, get_comparison_windows, get_date_range
from src.rules import get_active_config

def get_total_sales_summary(days: int = 30, store_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculates total sales revenue, units sold, and average daily revenue for given window."""
    conn = get_connection()
    cursor = conn.cursor()
    latest_date = get_latest_date()
    start_date, end_date = get_date_range(latest_date, days)

    query = """
    SELECT 
        COALESCE(SUM(quantity_sold), 0) as total_units,
        COALESCE(ROUND(SUM(revenue), 2), 0.0) as total_revenue,
        COUNT(DISTINCT date) as days_recorded
    FROM sales
    WHERE date >= ? AND date <= ?
    """
    params = [start_date, end_date]
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)

    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    total_units = int(row["total_units"])
    total_rev = float(row["total_revenue"])
    days_recorded = max(1, int(row["days_recorded"]))

    return {
        "period": f"{start_date} to {end_date}",
        "days": days,
        "total_units": total_units,
        "total_revenue": total_rev,
        "daily_average_revenue": round(total_rev / days_recorded, 2),
        "daily_average_units": round(total_units / days_recorded, 2)
    }

def get_daily_sales_series(days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns daily time-series of units sold and revenue for trend charts."""
    conn = get_connection()
    cursor = conn.cursor()
    latest_date = get_latest_date()
    start_date, end_date = get_date_range(latest_date, days)

    query = """
    SELECT date, 
           SUM(quantity_sold) as total_units, 
           ROUND(SUM(revenue), 2) as total_revenue
    FROM sales
    WHERE date >= ? AND date <= ?
    """
    params = [start_date, end_date]
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)
    query += " GROUP BY date ORDER BY date ASC;"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_top_selling_products(limit: int = 5, days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns top N products ranked by total revenue."""
    conn = get_connection()
    cursor = conn.cursor()
    latest_date = get_latest_date()
    start_date, end_date = get_date_range(latest_date, days)

    query = """
    SELECT p.product_id, p.product_name, p.category, p.price,
           SUM(s.quantity_sold) as total_units,
           ROUND(SUM(s.revenue), 2) as total_revenue
    FROM sales s
    JOIN products p ON s.product_id = p.product_id
    WHERE s.date >= ? AND s.date <= ?
    """
    params = [start_date, end_date]
    if store_id:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += f" GROUP BY p.product_id ORDER BY total_revenue DESC LIMIT {limit};"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_lowest_selling_products(limit: int = 5, days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns lowest performing products by units sold."""
    conn = get_connection()
    cursor = conn.cursor()
    latest_date = get_latest_date()
    start_date, end_date = get_date_range(latest_date, days)

    query = """
    SELECT p.product_id, p.product_name, p.category, p.price,
           COALESCE(SUM(s.quantity_sold), 0) as total_units,
           COALESCE(ROUND(SUM(s.revenue), 2), 0.0) as total_revenue
    FROM products p
    LEFT JOIN sales s ON p.product_id = s.product_id AND s.date >= ? AND s.date <= ?
    """
    params = [start_date, end_date]
    if store_id:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += f" GROUP BY p.product_id ORDER BY total_units ASC, total_revenue ASC LIMIT {limit};"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_category_sales(days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns sales breakdown grouped by category."""
    conn = get_connection()
    cursor = conn.cursor()
    latest_date = get_latest_date()
    start_date, end_date = get_date_range(latest_date, days)

    query = """
    SELECT p.category, 
           SUM(s.quantity_sold) as total_units, 
           ROUND(SUM(s.revenue), 2) as total_revenue
    FROM sales s
    JOIN products p ON s.product_id = p.product_id
    WHERE s.date >= ? AND s.date <= ?
    """
    params = [start_date, end_date]
    if store_id:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += " GROUP BY p.category ORDER BY total_revenue DESC;"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def compare_sales_periods(
    window_days: int = 7,
    store_id: Optional[str] = None,
    product_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes deterministic period-over-period comparison.
    e.g. Current 7 days vs Previous 7 days.
    """
    latest_date = get_latest_date()
    curr_start, curr_end, prev_start, prev_end = get_comparison_windows(latest_date, window_days)

    conn = get_connection()
    cursor = conn.cursor()

    # Query Current Period
    curr_q = "SELECT COALESCE(SUM(quantity_sold), 0), COALESCE(SUM(revenue), 0.0) FROM sales WHERE date >= ? AND date <= ?"
    params_c = [curr_start, curr_end]
    if store_id:
        curr_q += " AND store_id = ?"
        params_c.append(store_id)
    if product_id:
        curr_q += " AND product_id = ?"
        params_c.append(product_id)
    cursor.execute(curr_q, params_c)
    row_c = cursor.fetchone()
    curr_units, curr_rev = int(row_c[0]), round(float(row_c[1]), 2)

    # Query Previous Period
    prev_q = "SELECT COALESCE(SUM(quantity_sold), 0), COALESCE(SUM(revenue), 0.0) FROM sales WHERE date >= ? AND date <= ?"
    params_p = [prev_start, prev_end]
    if store_id:
        prev_q += " AND store_id = ?"
        params_p.append(store_id)
    if product_id:
        prev_q += " AND product_id = ?"
        params_p.append(product_id)
    cursor.execute(prev_q, params_p)
    row_p = cursor.fetchone()
    prev_units, prev_rev = int(row_p[0]), round(float(row_p[1]), 2)

    conn.close()

    pct_units = calc_pct_change(curr_units, prev_units)
    pct_rev = calc_pct_change(curr_rev, prev_rev)

    if pct_rev > 2.0:
        trend = "increase"
    elif pct_rev < -2.0:
        trend = "decrease"
    else:
        trend = "stable"

    return {
        "comparison": f"Current {window_days}d vs Previous {window_days}d",
        "current_period": f"{curr_start} to {curr_end}",
        "previous_period": f"{prev_start} to {prev_end}",
        "current_units": curr_units,
        "previous_units": prev_units,
        "units_change_percent": pct_units,
        "current_revenue": curr_rev,
        "previous_revenue": prev_rev,
        "revenue_change_percent": pct_rev,
        "trend": trend
    }
