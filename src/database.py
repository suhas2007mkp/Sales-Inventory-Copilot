"""
Database management for Sales & Inventory Copilot (PS03)
Handles SQLite database initialization, CSV ingestion, and high-performance querying.
"""
import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "retail_copilot.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reload: bool = False):
    """Initialize SQLite tables and load data from CSV if empty or force_reload is True."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        store_id TEXT PRIMARY KEY,
        store_name TEXT NOT NULL,
        location TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        supplier TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        store_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        quantity_sold INTEGER NOT NULL,
        revenue REAL NOT NULL,
        FOREIGN KEY (store_id) REFERENCES stores(store_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        store_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        stock_quantity INTEGER NOT NULL,
        FOREIGN KEY (store_id) REFERENCES stores(store_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    # Create indexes for fast lookup and aggregation
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_prod_store ON sales(product_id, store_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_prod_store ON inventory(product_id, store_id);")
    conn.commit()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM products;")
    prod_count = cursor.fetchone()[0]

    if prod_count == 0 or force_reload:
        print("[DB] Loading CSV data into SQLite database...")
        stores_csv = os.path.join(DATA_DIR, "stores.csv")
        products_csv = os.path.join(DATA_DIR, "products.csv")
        sales_csv = os.path.join(DATA_DIR, "sales.csv")
        inventory_csv = os.path.join(DATA_DIR, "inventory.csv")

        if os.path.exists(stores_csv):
            df_stores = pd.read_csv(stores_csv)
            df_stores.to_sql("stores", conn, if_exists="replace", index=False)

        if os.path.exists(products_csv):
            df_prods = pd.read_csv(products_csv)
            df_prods.to_sql("products", conn, if_exists="replace", index=False)

        if os.path.exists(sales_csv):
            df_sales = pd.read_csv(sales_csv)
            df_sales.to_sql("sales", conn, if_exists="replace", index=False)

        if os.path.exists(inventory_csv):
            df_inv = pd.read_csv(inventory_csv)
            df_inv.to_sql("inventory", conn, if_exists="replace", index=False)

        conn.commit()
        print(f"[DB] Initialized database at {DB_PATH}")

    conn.close()

def get_stores() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT store_id, store_name, location FROM stores ORDER BY store_id;")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_products() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, product_name, category, price, supplier FROM products ORDER BY product_id;")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_latest_date() -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM sales;")
    latest = cursor.fetchone()[0]
    conn.close()
    return latest or "2026-09-04"

def get_sales_summary(days: int = 30, store_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    latest_date = get_latest_date()
    query = """
    SELECT 
        SUM(quantity_sold) as total_units,
        SUM(revenue) as total_revenue,
        COUNT(DISTINCT date) as days_count
    FROM sales
    WHERE date >= date(?, '-' || ? || ' days')
    """
    params = [latest_date, days - 1]
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)

    cursor = conn.cursor()
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return {
        "total_units": row["total_units"] or 0,
        "total_revenue": round(row["total_revenue"] or 0.0, 2),
        "days_count": row["days_count"] or 0
    }
