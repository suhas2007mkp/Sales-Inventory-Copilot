"""
Automated Backend Test Suite for Sales & Inventory Copilot (PS03)
Validates:
1. Low stock & critical stockout forecasting
2. Overstock detection
3. Slow-moving inventory
4. Sales increase, decrease, spikes, and drops
5. Unknown product and empty query handling
6. Zero sales division-by-zero protection
7. API response contracts and endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app import app
from src.utils import safe_divide, calc_pct_change
from src.rules import evaluate_low_stock, evaluate_overstock, evaluate_slow_moving, InventoryConfig
from src.inventory_service import get_product_inventory_metrics, get_stockout_predictions
from src.sales_service import compare_sales_periods, get_top_selling_products
from src.chat_service import handle_chat_query

client = TestClient(app)

# 1. System Health & Core Endpoints
def test_health_check():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["track_id"] == "PS03"

def test_dashboard_summary():
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["total_products"] == 20
    assert data["total_stores"] == 3
    assert data["today_sales_revenue"] > 0
    assert data["active_alerts_count"] > 0

def test_products_list():
    res = client.get("/api/products")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 20
    for p in data:
        assert "days_of_stock_display" in p
        assert "status" in p

def test_product_detail_found_and_not_found():
    # Valid product
    res = client.get("/api/products/PRD001")
    assert res.status_code == 200
    assert res.json()["product"]["product_id"] == "PRD001"

    # Unknown product
    res_err = client.get("/api/products/NON_EXISTENT_SKU")
    assert res_err.status_code == 404

def test_inventory_overview():
    res = client.get("/api/inventory")
    assert res.status_code == 200
    data = res.json()
    assert data["total_stock_units"] > 0
    assert data["total_inventory_value_inr"] > 0

def test_sales_summary():
    res = client.get("/api/sales?days=14")
    assert res.status_code == 200
    data = res.json()
    assert data["days"] == 14
    assert data["total_units"] > 0

def test_analytics_sales_and_inventory():
    res_s = client.get("/api/analytics/sales")
    assert res_s.status_code == 200
    assert "comparison_7d_vs_prev7d" in res_s.json()

    res_i = client.get("/api/analytics/inventory")
    assert res_i.status_code == 200
    assert "stockout_predictions" in res_i.json()

# 2. Math & Safe Division Protections
def test_safe_divide():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(10, 0) == 0.0
    assert safe_divide(10, None) == 0.0
    assert safe_divide(10, 0, default=999.0) == 999.0

def test_calc_pct_change():
    assert calc_pct_change(150, 100) == 50.0
    assert calc_pct_change(50, 100) == -50.0
    assert calc_pct_change(10, 0) == 100.0
    assert calc_pct_change(0, 0) == 0.0

# 3. Deterministic Inventory Rules
def test_low_stock_evaluation():
    cfg = InventoryConfig(low_stock_days_threshold=5.0, critical_stock_days_threshold=2.0)
    # Stock 10, daily sales 5 -> 2.0 days (Critical)
    alert = evaluate_low_stock("Test Product", current_stock=10, avg_daily_sales=5.0, config=cfg)
    assert alert is not None
    assert alert["alert_type"] == "LOW_STOCK"
    assert alert["severity"] == "URGENT"
    assert alert["supporting_numbers"]["days_of_stock"] == 2.0

    # Stock 50, daily sales 2 -> 25 days (No alert)
    alert_healthy = evaluate_low_stock("Healthy Product", current_stock=50, avg_daily_sales=2.0, config=cfg)
    assert alert_healthy is None

def test_overstock_evaluation():
    cfg = InventoryConfig(overstock_days_threshold=45.0, slow_moving_min_stock=20)
    # Stock 200, daily sales 1 -> 200 days (Overstocked)
    alert = evaluate_overstock("Overstock Product", current_stock=200, avg_daily_sales=1.0, config=cfg)
    assert alert is not None
    assert alert["alert_type"] == "OVERSTOCK"
    assert alert["severity"] == "WARNING"

def test_slow_moving_evaluation():
    cfg = InventoryConfig(slow_moving_daily_sales=0.15, slow_moving_min_stock=20)
    alert = evaluate_slow_moving("Stagnant Item", current_stock=60, historical_daily_sales=0.05, total_units_sold_30d=1, config=cfg)
    assert alert is not None
    assert alert["alert_type"] == "SLOW_MOVING"

# 4. Period Comparisons & Spikes/Drops
def test_period_comparison():
    comp = compare_sales_periods(window_days=7)
    assert "current_units" in comp
    assert "previous_units" in comp
    assert "trend" in comp
    assert comp["trend"] in ("increase", "decrease", "stable")

# 5. Natural Language Copilot Queries & Evidence
def test_copilot_running_out():
    res = client.post("/api/chat", json={"question": "What products are running out?"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "data_used" in data
    assert len(data["recommendations"]) > 0

def test_copilot_epistemic_honesty():
    res = client.post("/api/chat", json={"question": "Why did sales decrease for Dettol Handwash?"})
    assert res.status_code == 200
    data = res.json()
    assert data["insufficient_data"] is True
    ans = data["answer"].lower()
    assert "not contain enough information" in ans or "not have enough data" in ans or "insufficient" in ans

def test_copilot_best_seller():
    res = client.post("/api/chat", json={"question": "Which product sold the most this month?"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data

def test_copilot_empty_question():
    res = client.post("/api/chat", json={"question": "   "})
    assert res.status_code == 400
