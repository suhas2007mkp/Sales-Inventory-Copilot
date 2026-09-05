"""
Sales & Inventory Copilot (PS03) - Main Backend Application
Serves REST API and modern static dashboard frontend.
Starts with: python app.py -> http://localhost:8000
"""
import os
import uvicorn
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.database import init_db, get_stores, get_connection
from src.rules import DEFAULT_CONFIG, InventoryConfig
from src.analytics import (
    get_dashboard_summary,
    get_product_analytics,
    get_all_alerts,
    get_sales_trend,
    get_sales_by_category,
    get_top_selling_products,
    get_stock_levels_chart_data
)
from src.schemas import ChatRequest, ChatResponse

# Initialize database on startup
init_db()

app = FastAPI(
    title="Sales & Inventory Copilot",
    description="Intelligent retail copilot with deterministic analytics & grounded AI recommendations",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# System runtime config
runtime_config = InventoryConfig()

# Mount static files
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "Sales & Inventory Copilot",
        "track_id": "PS03",
        "version": "1.0.0"
    }

@app.get("/api/stores")
def list_stores():
    """Returns list of retail stores."""
    return get_stores()

@app.get("/api/dashboard")
def dashboard_overview(store_id: Optional[str] = None):
    """Returns key performance indicators and alert summary."""
    try:
        summary = get_dashboard_summary(store_id=store_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
def list_products(
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None
):
    """Returns all products with calculated velocity, days of stock, and health status."""
    products = get_product_analytics(store_id=store_id, config=runtime_config)
    if category and category != "ALL":
        products = [p for p in products if p["category"].lower() == category.lower()]
    if status and status != "ALL":
        products = [p for p in products if p["status"].upper() == status.upper()]
    return products

@app.get("/api/alerts")
def list_alerts(
    store_id: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None
):
    """Returns actionable alerts with findings, numbers, assumptions, and actions."""
    alerts = get_all_alerts(store_id=store_id, config=runtime_config)
    if severity and severity != "ALL":
        alerts = [a for a in alerts if a.get("severity") == severity]
    if alert_type and alert_type != "ALL":
        alerts = [a for a in alerts if a.get("alert_type") == alert_type]
    return alerts

@app.get("/api/sales/trends")
def sales_trend(days: int = Query(default=30, ge=7, le=60), store_id: Optional[str] = None):
    """Returns daily revenue & quantity sold for trend chart."""
    return get_sales_trend(days=days, store_id=store_id)

@app.get("/api/sales/categories")
def category_distribution(store_id: Optional[str] = None):
    """Returns 30-day sales by category for doughnut chart."""
    return get_sales_by_category(store_id=store_id)

@app.get("/api/charts/top-products")
def top_products(limit: int = Query(default=5, ge=1, le=20), store_id: Optional[str] = None):
    """Returns top performing products by revenue."""
    return get_top_selling_products(limit=limit, store_id=store_id)

@app.get("/api/charts/stock-levels")
def stock_levels_comparison(store_id: Optional[str] = None):
    """Returns current inventory vs safety stock levels."""
    return get_stock_levels_chart_data(store_id=store_id)

@app.get("/api/config")
def get_config():
    """Returns active thresholds."""
    return runtime_config.model_dump()

@app.post("/api/config")
def update_config(config_data: Dict[str, Any] = Body(...)):
    """Allows manager to configure thresholds (e.g. low stock days threshold)."""
    global runtime_config
    if "low_stock_days_threshold" in config_data:
        runtime_config.low_stock_days_threshold = float(config_data["low_stock_days_threshold"])
    if "overstock_days_threshold" in config_data:
        runtime_config.overstock_days_threshold = float(config_data["overstock_days_threshold"])
    if "slow_moving_daily_sales" in config_data:
        runtime_config.slow_moving_daily_sales = float(config_data["slow_moving_daily_sales"])
    if "spike_ratio_threshold" in config_data:
        runtime_config.spike_ratio_threshold = float(config_data["spike_ratio_threshold"])
    if "drop_ratio_threshold" in config_data:
        runtime_config.drop_ratio_threshold = float(config_data["drop_ratio_threshold"])
    return {"message": "Configuration updated successfully", "config": runtime_config.model_dump()}

@app.post("/api/chat", response_model=ChatResponse)
def copilot_chat(request: ChatRequest):
    """
    Intelligent Sales & Inventory Copilot chat endpoint.
    Performs deterministic calculations in Python & invokes Gemini with strict grounding.
    """
    from src.gemini_service import query_copilot
    return query_copilot(question=request.question, store_id=request.store_id)

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found, API is running."}

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Sales & Inventory Copilot (PS03)")
    print("Access application at: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
