"""
Deterministic Analytics Engine for Sales & Inventory Copilot (PS03)
Calculates exact mathematical metrics using Python, pandas, and SQLite.
Zero hallucinations: every calculation is strictly grounded in the database.
"""
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from src.database import get_connection, get_latest_date, init_db
from src.rules import (
    DEFAULT_CONFIG,
    InventoryConfig,
    evaluate_low_stock,
    evaluate_overstock,
    evaluate_slow_moving,
    evaluate_sales_spike,
    evaluate_sales_drop
)
from src.schemas import DashboardSummary, Recommendation, SupportingNumbers

def get_product_analytics(store_id: Optional[str] = None, config: InventoryConfig = DEFAULT_CONFIG) -> List[Dict[str, Any]]:
    """
    Computes deterministic inventory velocity and metrics for all products.
    """
    conn = get_connection()
    latest_date_str = get_latest_date()
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    
    date_7d_ago = (latest_date - timedelta(days=6)).strftime("%Y-%m-%d")
    date_30d_ago = (latest_date - timedelta(days=29)).strftime("%Y-%m-%d")

    # 1. Fetch products
    products_df = pd.read_sql_query("SELECT product_id, product_name, category, price, supplier FROM products", conn)

    # 2. Fetch inventory
    inv_query = "SELECT product_id, store_id, stock_quantity FROM inventory WHERE date = (SELECT MAX(date) FROM inventory)"
    if store_id:
        inv_query += f" AND store_id = '{store_id}'"
    inv_df = pd.read_sql_query(inv_query, conn)
    
    # Aggregate inventory by product (if all stores or single store)
    inv_agg = inv_df.groupby("product_id")["stock_quantity"].sum().reset_index()

    # 3. Fetch sales in last 30 days
    sales_query = f"""
    SELECT product_id, store_id, date, quantity_sold, revenue 
    FROM sales 
    WHERE date >= '{date_30d_ago}'
    """
    if store_id:
        sales_query += f" AND store_id = '{store_id}'"
    sales_df = pd.read_sql_query(sales_query, conn)

    conn.close()

    # Merge products and inventory
    merged = pd.merge(products_df, inv_agg, on="product_id", how="left").fillna({"stock_quantity": 0})
    merged["stock_quantity"] = merged["stock_quantity"].astype(int)

    # Calculate 7-day and 30-day velocity per product
    results = []
    for _, row in merged.iterrows():
        pid = row["product_id"]
        pname = row["product_name"]
        cat = row["category"]
        price = float(row["price"])
        supplier = row["supplier"]
        stock = int(row["stock_quantity"])

        p_sales_30d = sales_df[sales_df["product_id"] == pid]
        units_30d = int(p_sales_30d["quantity_sold"].sum()) if not p_sales_30d.empty else 0
        rev_30d = round(float(p_sales_30d["revenue"].sum()), 2) if not p_sales_30d.empty else 0.0
        avg_daily_30d = round(units_30d / 30.0, 2)

        p_sales_7d = p_sales_30d[p_sales_30d["date"] >= date_7d_ago]
        units_7d = int(p_sales_7d["quantity_sold"].sum()) if not p_sales_7d.empty else 0
        rev_7d = round(float(p_sales_7d["revenue"].sum()), 2) if not p_sales_7d.empty else 0.0
        avg_daily_7d = round(units_7d / 7.0, 2)

        # Primary velocity metric uses recent 7 days if active, else 30 days
        effective_daily_sales = avg_daily_7d if avg_daily_7d > 0 else avg_daily_30d
        
        # Days of stock calculation
        if effective_daily_sales > 0:
            days_of_stock = round(stock / effective_daily_sales, 1)
        else:
            days_of_stock = 999.0 if stock > 0 else 0.0

        # Change %
        if avg_daily_30d > 0:
            sales_change_pct = round(((avg_daily_7d - avg_daily_30d) / avg_daily_30d) * 100, 1)
        else:
            sales_change_pct = 100.0 if avg_daily_7d > 0 else 0.0

        # Determine health status
        status = "HEALTHY"
        if stock > 0 and days_of_stock < config.low_stock_days_threshold:
            status = "LOW_STOCK"
        elif days_of_stock > config.overstock_days_threshold and stock >= 20:
            status = "OVERSTOCK"
        elif stock >= config.slow_moving_min_stock and avg_daily_30d <= config.slow_moving_daily_sales:
            status = "SLOW_MOVING"
        elif avg_daily_30d >= 0.3 and (avg_daily_7d / avg_daily_30d) >= config.spike_ratio_threshold:
            status = "SALES_SPIKE"
        elif avg_daily_30d >= 0.5 and (avg_daily_7d / avg_daily_30d) <= config.drop_ratio_threshold:
            status = "SALES_DROP"

        results.append({
            "product_id": pid,
            "product_name": pname,
            "category": cat,
            "price": price,
            "supplier": supplier,
            "current_stock": stock,
            "units_sold_30d": units_30d,
            "revenue_30d": rev_30d,
            "avg_daily_sales_30d": avg_daily_30d,
            "units_sold_7d": units_7d,
            "revenue_7d": rev_7d,
            "avg_daily_sales_7d": avg_daily_7d,
            "effective_daily_sales": effective_daily_sales,
            "days_of_stock": days_of_stock if days_of_stock < 999 else None,
            "days_of_stock_display": f"{days_of_stock:.1f}" if days_of_stock < 999 else "> 300 (Idle)",
            "sales_change_pct": sales_change_pct,
            "status": status
        })

    return results

def get_all_alerts(store_id: Optional[str] = None, config: InventoryConfig = DEFAULT_CONFIG) -> List[Dict[str, Any]]:
    """
    Evaluates all products against rules and returns a structured list of alerts & recommendations.
    """
    products_metrics = get_product_analytics(store_id=store_id, config=config)
    alerts = []

    # Map store name if store_id provided
    store_name = None
    if store_id:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT store_name FROM stores WHERE store_id = ?", (store_id,))
        row = cursor.fetchone()
        if row:
            store_name = row["store_name"]
        conn.close()

    for p in products_metrics:
        pname = p["product_name"]
        pid = p["product_id"]
        stock = p["current_stock"]
        avg_7d = p["avg_daily_sales_7d"]
        avg_30d = p["avg_daily_sales_30d"]
        units_30d = p["units_sold_30d"]

        # Check Low Stock
        alert = evaluate_low_stock(pname, stock, avg_7d or avg_30d, config, store_name)
        if alert:
            alert["product_id"] = pid
            alert["product_name"] = pname
            alert["store_id"] = store_id
            alert["store_name"] = store_name
            alerts.append(alert)
            continue  # Primary concern for this product

        # Check Overstock
        alert = evaluate_overstock(pname, stock, avg_30d, config, store_name)
        if alert:
            alert["product_id"] = pid
            alert["product_name"] = pname
            alert["store_id"] = store_id
            alert["store_name"] = store_name
            alerts.append(alert)

        # Check Slow Moving
        alert = evaluate_slow_moving(pname, stock, avg_30d, units_30d, config, store_name)
        if alert:
            alert["product_id"] = pid
            alert["product_name"] = pname
            alert["store_id"] = store_id
            alert["store_name"] = store_name
            alerts.append(alert)

        # Check Sales Spike
        alert = evaluate_sales_spike(pname, avg_7d, avg_30d, stock, config, store_name)
        if alert:
            alert["product_id"] = pid
            alert["product_name"] = pname
            alert["store_id"] = store_id
            alert["store_name"] = store_name
            alerts.append(alert)

        # Check Sales Drop
        alert = evaluate_sales_drop(pname, avg_7d, avg_30d, stock, config, store_name)
        if alert:
            alert["product_id"] = pid
            alert["product_name"] = pname
            alert["store_id"] = store_id
            alert["store_name"] = store_name
            alerts.append(alert)

    # Sort alerts: URGENT first, then WARNING, then OPPORTUNITY
    severity_order = {"URGENT": 0, "WARNING": 1, "OPPORTUNITY": 2, "INFO": 3}
    alerts.sort(key=lambda x: severity_order.get(x.get("severity", "INFO"), 4))
    return alerts

def get_dashboard_summary(store_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes top-level summary metrics for dashboard KPIs.
    """
    conn = get_connection()
    latest_date = get_latest_date()
    
    # Store count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stores;")
    total_stores = cursor.fetchone()[0]

    # Today's sales (sales on the latest date in database)
    today_query = "SELECT SUM(revenue), SUM(quantity_sold) FROM sales WHERE date = ?"
    params = [latest_date]
    if store_id:
        today_query += " AND store_id = ?"
        params.append(store_id)
    cursor.execute(today_query, params)
    row = cursor.fetchone()
    today_rev = round(row[0] or 0.0, 2)
    today_units = int(row[1] or 0)
    conn.close()

    metrics = get_product_analytics(store_id=store_id)
    alerts = get_all_alerts(store_id=store_id)

    total_products = len(metrics)
    low_stock = sum(1 for p in metrics if p["status"] == "LOW_STOCK")
    overstock = sum(1 for p in metrics if p["status"] == "OVERSTOCK")
    slow_moving = sum(1 for p in metrics if p["status"] == "SLOW_MOVING")
    sales_spikes = sum(1 for p in metrics if p["status"] == "SALES_SPIKE")
    sales_drops = sum(1 for p in metrics if p["status"] == "SALES_DROP")

    return {
        "total_products": total_products,
        "total_stores": total_stores if not store_id else 1,
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

def get_sales_trend(days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns time-series daily sales for Chart.js trend chart.
    """
    conn = get_connection()
    latest_date = get_latest_date()
    query = """
    SELECT date, SUM(quantity_sold) as total_units, ROUND(SUM(revenue), 2) as total_revenue
    FROM sales
    WHERE date >= date(?, '-' || ? || ' days')
    """
    params = [latest_date, days - 1]
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)
    query += " GROUP BY date ORDER BY date ASC;"

    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_sales_by_category(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns aggregate revenue and units sold by category in past 30 days.
    """
    conn = get_connection()
    latest_date = get_latest_date()
    query = """
    SELECT p.category, SUM(s.quantity_sold) as total_units, ROUND(SUM(s.revenue), 2) as total_revenue
    FROM sales s
    JOIN products p ON s.product_id = p.product_id
    WHERE s.date >= date(?, '-29 days')
    """
    params = [latest_date]
    if store_id:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += " GROUP BY p.category ORDER BY total_revenue DESC;"

    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_top_selling_products(limit: int = 5, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns top N products by revenue in past 30 days.
    """
    conn = get_connection()
    latest_date = get_latest_date()
    query = """
    SELECT p.product_id, p.product_name, p.category, SUM(s.quantity_sold) as total_units, ROUND(SUM(s.revenue), 2) as total_revenue
    FROM sales s
    JOIN products p ON s.product_id = p.product_id
    WHERE s.date >= date(?, '-29 days')
    """
    params = [latest_date]
    if store_id:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += f" GROUP BY p.product_id ORDER BY total_revenue DESC LIMIT {limit};"

    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_stock_levels_chart_data(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns stock level data compared to 7-day safety buffer for top 10 products.
    """
    metrics = get_product_analytics(store_id=store_id)
    # Sort by stock or status
    chart_data = []
    for p in metrics:
        safety_stock = int(round((p["avg_daily_sales_7d"] or p["avg_daily_sales_30d"]) * 7))
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
