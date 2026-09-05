"""
Database management for Sales & Inventory Copilot (PS03)
Handles SQLite database initialization, CSV ingestion, and safe parameterized querying.
Zero SQL injection risk: all dynamic values use parameter bindings (?).
"""
import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
from src.utils import setup_logger

logger = setup_logger("database")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "retail_copilot.db")

def get_connection() -> sqlite3.Connection:
    """Creates a thread-safe SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reload: bool = False):
    """
    Initializes SQLite tables with strict primary keys and indexes.
    Loads data from CSV files if empty or if force_reload is True.
    """
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

    # Performance indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_prod_date ON sales(product_id, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_prod_store ON sales(product_id, store_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_prod_store ON inventory(product_id, store_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_date ON inventory(date);")
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM products;")
    prod_count = cursor.fetchone()[0]

    if prod_count == 0 or force_reload:
        logger.info("Ingesting synthetic retail data into SQLite tables...")
        stores_csv = os.path.join(DATA_DIR, "stores.csv")
        products_csv = os.path.join(DATA_DIR, "products.csv")
        sales_csv = os.path.join(DATA_DIR, "sales.csv")
        inventory_csv = os.path.join(DATA_DIR, "inventory.csv")

        # Clear existing data safely before append if force_reload
        if force_reload:
            cursor.execute("DELETE FROM sales;")
            cursor.execute("DELETE FROM inventory;")
            cursor.execute("DELETE FROM products;")
            cursor.execute("DELETE FROM stores;")
            conn.commit()

        if os.path.exists(stores_csv):
            df_stores = pd.read_csv(stores_csv)
            df_stores.to_sql("stores", conn, if_exists="append", index=False)

        if os.path.exists(products_csv):
            df_prods = pd.read_csv(products_csv)
            df_prods.to_sql("products", conn, if_exists="append", index=False)

        if os.path.exists(sales_csv):
            df_sales = pd.read_csv(sales_csv)
            df_sales.to_sql("sales", conn, if_exists="append", index=False)

        if os.path.exists(inventory_csv):
            df_inv = pd.read_csv(inventory_csv)
            df_inv.to_sql("inventory", conn, if_exists="append", index=False)

        conn.commit()
        logger.info(f"Database successfully populated at {DB_PATH}")

    conn.close()

# ----------------- Safe Parameterized Query Helpers -----------------
def get_stores() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT store_id, store_name, location FROM stores ORDER BY store_id ASC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_store_by_id(store_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT store_id, store_name, location FROM stores WHERE store_id = ?;", (store_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_products(category: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if category and category.upper() != "ALL":
        cursor.execute("SELECT product_id, product_name, category, price, supplier FROM products WHERE category = ? ORDER BY product_id ASC;", (category,))
    else:
        cursor.execute("SELECT product_id, product_name, category, price, supplier FROM products ORDER BY product_id ASC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, product_name, category, price, supplier FROM products WHERE product_id = ?;", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_latest_date() -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM sales;")
    res = cursor.fetchone()
    conn.close()
    return (res[0] if res and res[0] else "2026-09-04")

def get_inventory_snapshot(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns the latest stock quantities per product, optionally filtered by store."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
    SELECT i.product_id, p.product_name, p.category, p.price, p.supplier,
           SUM(i.stock_quantity) as total_stock,
           i.date as inventory_date
    FROM inventory i
    JOIN products p ON i.product_id = p.product_id
    WHERE i.date = (SELECT MAX(date) FROM inventory)
    """
    params = []
    if store_id:
        query += " AND i.store_id = ?"
        params.append(store_id)
    query += " GROUP BY i.product_id ORDER BY i.product_id ASC;"
    
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_sales_aggregate(
    start_date: str,
    end_date: str,
    store_id: Optional[str] = None,
    product_id: Optional[str] = None
) -> Dict[str, Any]:
    """Safe parameterized query computing total units, total revenue, and distinct days."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
    SELECT 
        COALESCE(SUM(quantity_sold), 0) as total_units,
        COALESCE(ROUND(SUM(revenue), 2), 0.0) as total_revenue,
        COUNT(DISTINCT date) as days_count
    FROM sales
    WHERE date >= ? AND date <= ?
    """
    params = [start_date, end_date]
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)
    if product_id:
        query += " AND product_id = ?"
        params.append(product_id)

    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return {
        "total_units": int(row["total_units"]),
        "total_revenue": float(row["total_revenue"]),
        "days_count": int(row["days_count"])
    }
