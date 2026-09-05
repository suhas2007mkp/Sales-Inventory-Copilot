"""
Sales & Inventory Copilot (PS03) - Main Backend Application
Serves REST API, advanced analytics services, and modern static dashboard frontend.
Starts with: python app.py -> http://localhost:8000
"""
import os
import uvicorn
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.utils import setup_logger, load_env_file
from src.database import init_db, get_stores, get_product_by_id, get_products
from src.rules import get_active_config, set_active_config
from src.sales_service import (
    get_total_sales_summary,
    get_daily_sales_series,
    get_top_selling_products,
    get_lowest_selling_products,
    get_category_sales,
    compare_sales_periods
)
from src.inventory_service import (
    get_product_inventory_metrics,
    get_stockout_predictions,
    get_inventory_overview
)
from src.recommendation_service import generate_recommendations
from src.chat_service import handle_chat_query
from src.analytics import (
    get_dashboard_summary,
    get_stock_levels_chart_data
)
from src.schemas import (
    Store, Product, Recommendation, DashboardSummary,
    SalesAnalyticsResponse, InventoryAnalyticsResponse,
    ChatRequest, ChatResponse
)

# Load environment & configure logger
load_env_file()
logger = setup_logger("app")

# Initialize database on startup
init_db()

app = FastAPI(
    title="Sales & Inventory Copilot",
    description="Intelligent retail copilot with deterministic analytics & grounded AI recommendations",
    version="2.0.0"
)

# CORS Middleware (secure local access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Mount static frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ----------------- System & Health Endpoints -----------------
@app.get("/api/health")
def health_check():
    """Health check endpoint confirming API status and version."""
    return {
        "status": "ok",
        "service": "Sales & Inventory Copilot",
        "track_id": "PS03",
        "version": "2.0.0"
    }

# ----------------- Core Entity Endpoints -----------------
@app.get("/api/stores", response_model=List[Store])
def list_stores():
    """Returns all retail stores in the network."""
    return get_stores()

@app.get("/api/products")
def list_products(
    store_id: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None
):
    """Returns product catalogue with calculated run-rates, days of stock, and health status."""
    products = get_product_inventory_metrics(store_id=store_id)
    if category and category.upper() != "ALL":
        products = [p for p in products if p["category"].lower() == category.lower()]
    if status and status.upper() != "ALL":
        products = [p for p in products if p["status"].upper() == status.upper()]
    return products

@app.get("/api/products/{product_id}")
def product_detail(product_id: str, store_id: Optional[str] = None):
    """Returns single product detail, current inventory, velocity, and health alerts."""
    all_metrics = get_product_inventory_metrics(store_id=store_id)
    p_data = next((p for p in all_metrics if p["product_id"] == product_id), None)
    if not p_data:
        raise HTTPException(status_code=404, detail=f"Product with ID '{product_id}' not found.")
    
    recs = [r for r in generate_recommendations(store_id=store_id) if r["product_id"] == product_id]
    return {
        "product": p_data,
        "recommendations": recs
    }

@app.get("/api/inventory")
def inventory_snapshot(store_id: Optional[str] = None):
    """Returns aggregate inventory units, total valuation in INR, and health distribution."""
    return get_inventory_overview(store_id=store_id)

@app.get("/api/sales")
def sales_summary(days: int = Query(default=30, ge=1, le=90), store_id: Optional[str] = None):
    """Returns aggregate sales metrics for specified time window."""
    return get_total_sales_summary(days=days, store_id=store_id)

# ----------------- Operational Dashboard & Alerts -----------------
@app.get("/api/dashboard", response_model=DashboardSummary)
def dashboard_overview(store_id: Optional[str] = None):
    """Returns executive KPI metrics and active alert counts for the dashboard."""
    try:
        return get_dashboard_summary(store_id=store_id)
    except Exception as e:
        logger.error(f"Error computing dashboard overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard summary metrics.")

@app.get("/api/alerts")
def list_alerts(
    store_id: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None
):
    """Returns actionable alerts with findings, numbers, assumptions, and suggested actions."""
    alerts = generate_recommendations(store_id=store_id)
    if severity and severity.upper() != "ALL":
        alerts = [a for a in alerts if a.get("severity") == severity]
    if alert_type and alert_type.upper() != "ALL":
        alerts = [a for a in alerts if a.get("alert_type") == alert_type]
    return alerts

@app.get("/api/recommendations")
def list_recommendations(store_id: Optional[str] = None):
    """Deterministic business recommendations based on verified inventory and sales data."""
    return generate_recommendations(store_id=store_id)

# ----------------- Deep Analytics Endpoints -----------------
@app.get("/api/analytics/sales")
def analytics_sales(
    days: int = Query(default=30, ge=7, le=90),
    store_id: Optional[str] = None
):
    """Deep sales analytics: volume, revenue, 7-day period-over-period comparison, top/lowest sellers."""
    summary = get_total_sales_summary(days=days, store_id=store_id)
    comparison = compare_sales_periods(window_days=7, store_id=store_id)
    top_5 = get_top_selling_products(limit=5, days=days, store_id=store_id)
    lowest_5 = get_lowest_selling_products(limit=5, days=days, store_id=store_id)
    categories = get_category_sales(days=days, store_id=store_id)

    return {
        "summary": summary,
        "comparison_7d_vs_prev7d": comparison,
        "top_selling_products": top_5,
        "lowest_selling_products": lowest_5,
        "category_breakdown": categories
    }

@app.get("/api/analytics/inventory")
def analytics_inventory(
    threshold_days: Optional[float] = Query(default=None, ge=0.5, le=60.0),
    store_id: Optional[str] = None
):
    """Deep inventory analytics: stockout risk projections, overstock items, slow-moving SKUs."""
    overview = get_inventory_overview(store_id=store_id)
    stockouts = get_stockout_predictions(threshold_days=threshold_days, store_id=store_id)
    all_metrics = get_product_inventory_metrics(store_id=store_id)

    overstocked = [p for p in all_metrics if p["status"] == "OVERSTOCK"]
    slow_moving = [p for p in all_metrics if p["status"] == "SLOW_MOVING"]

    return {
        "overview": overview,
        "stockout_predictions": stockouts,
        "overstocked_products": overstocked,
        "slow_moving_products": slow_moving
    }

# ----------------- Chart.js Endpoints (Frontend Compatibility) -----------------
@app.get("/api/sales/trends")
def sales_trend(days: int = Query(default=30, ge=7, le=60), store_id: Optional[str] = None):
    """Returns daily revenue & quantity sold for time-series trend chart."""
    return get_daily_sales_series(days=days, store_id=store_id)

@app.get("/api/sales/categories")
def category_distribution(store_id: Optional[str] = None):
    """Returns 30-day sales by category for portfolio doughnut chart."""
    return get_category_sales(days=30, store_id=store_id)

@app.get("/api/charts/top-products")
def top_products(limit: int = Query(default=5, ge=1, le=20), store_id: Optional[str] = None):
    """Returns top performing products by revenue."""
    return get_top_selling_products(limit=limit, store_id=store_id)

@app.get("/api/charts/stock-levels")
def stock_levels_comparison(store_id: Optional[str] = None):
    """Returns current inventory vs safety stock buffer."""
    return get_stock_levels_chart_data(store_id=store_id)

# ----------------- Configuration Endpoints -----------------
@app.get("/api/config")
def get_config():
    """Returns active calculation thresholds."""
    return get_active_config().model_dump()

@app.post("/api/config")
def update_config(config_data: Dict[str, Any] = Body(...)):
    """Allows store managers to adjust thresholds live from the UI."""
    new_cfg = set_active_config(config_data)
    logger.info(f"Inventory thresholds updated: {new_cfg.model_dump()}")
    return {"message": "Configuration updated successfully", "config": new_cfg.model_dump()}

# ----------------- Copilot Chat Pipeline -----------------
@app.post("/api/chat", response_model=ChatResponse)
def copilot_chat(request: ChatRequest):
    """
    Intelligent Sales & Inventory Copilot chat endpoint.
    Performs deterministic calculations in Python & invokes Gemini with strict grounding.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    return handle_chat_query(question=request.question, store_id=request.store_id)

# ----------------- Static Frontend Delivery -----------------
@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found, API is running."}

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting Sales & Inventory Copilot (PS03)")
    logger.info("Access application at: http://localhost:8000")
    logger.info("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
