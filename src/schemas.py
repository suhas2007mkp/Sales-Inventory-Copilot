"""Pydantic schemas and data models for Sales & Inventory Copilot"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Store(BaseModel):
    store_id: str
    store_name: str
    location: str

class Product(BaseModel):
    product_id: str
    product_name: str
    category: str
    price: float
    supplier: str

class SaleRecord(BaseModel):
    date: str
    store_id: str
    product_id: str
    quantity_sold: int
    revenue: float

class InventoryRecord(BaseModel):
    date: str
    store_id: str
    product_id: str
    stock_quantity: int

class SupportingNumbers(BaseModel):
    current_stock: Optional[int] = None
    avg_daily_sales: Optional[float] = None
    days_of_stock: Optional[float] = None
    historical_avg_daily_sales: Optional[float] = None
    recent_avg_daily_sales: Optional[float] = None
    sales_change_pct: Optional[float] = None
    units_sold_recent: Optional[int] = None
    total_revenue_recent: Optional[float] = None
    threshold: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class Recommendation(BaseModel):
    finding: str
    supporting_numbers: SupportingNumbers
    assumption: str
    recommended_action: str
    alert_type: str  # LOW_STOCK, OVERSTOCK, SLOW_MOVING, SALES_SPIKE, SALES_DROP, NORMAL
    severity: str    # URGENT, WARNING, OPPORTUNITY, INFO
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    store_id: Optional[str] = None
    store_name: Optional[str] = None

class DashboardSummary(BaseModel):
    total_products: int
    total_stores: int
    today_sales_revenue: float
    today_units_sold: int
    low_stock_count: int
    overstock_count: int
    slow_moving_count: int
    sales_spikes_count: int
    sales_drops_count: int
    active_alerts_count: int

class ChatRequest(BaseModel):
    question: str
    store_id: Optional[str] = None

class ChatResponse(BaseModel):
    question: str
    answer: str
    data_used: Dict[str, Any]
    supporting_numbers: Optional[SupportingNumbers] = None
    recommendations: List[Recommendation] = Field(default_factory=list)
    insufficient_data: bool = False
    source: str = "deterministic_with_gemini"  # or "deterministic_fallback"
