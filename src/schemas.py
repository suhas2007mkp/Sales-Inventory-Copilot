"""
Pydantic schemas and data contracts for Sales & Inventory Copilot (PS03)
Ensures strict request/response validation and backward-compatibility with frontend.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# ----------------- Core Entities -----------------
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
    id: Optional[int] = None
    date: str
    store_id: str
    product_id: str
    quantity_sold: int
    revenue: float

class InventoryRecord(BaseModel):
    id: Optional[int] = None
    date: str
    store_id: str
    product_id: str
    stock_quantity: int

# ----------------- Evidence & Metrics -----------------
class EvidenceObject(BaseModel):
    source: str = Field(..., description="Data source tables used in calculation (e.g. sales, inventory)")
    period: Optional[str] = Field(None, description="Time window evaluated (e.g. 2026-08-05 to 2026-09-04)")
    product_id: Optional[str] = None
    store_id: Optional[str] = None
    calculation: str = Field(..., description="Deterministic formula applied")
    parameters: Optional[Dict[str, Any]] = None

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

# ----------------- Dashboard & Analytics Schemas -----------------
class DashboardSummary(BaseModel):
    total_products: int
    total_stores: int
    latest_date: str
    today_sales_revenue: float
    today_units_sold: int
    low_stock_count: int
    overstock_count: int
    slow_moving_count: int
    sales_spikes_count: int
    sales_drops_count: int
    active_alerts_count: int

class ProductAnalyticsItem(BaseModel):
    product_id: str
    product_name: str
    category: str
    price: float
    supplier: str
    current_stock: int
    units_sold_30d: int
    revenue_30d: float
    avg_daily_sales_30d: float
    units_sold_7d: int
    revenue_7d: float
    avg_daily_sales_7d: float
    effective_daily_sales: float
    days_of_stock: Optional[float] = None
    days_of_stock_display: str
    sales_change_pct: float
    status: str

class PeriodSalesComparison(BaseModel):
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    current_period: str
    previous_period: str
    current_units: int
    previous_units: int
    current_revenue: float
    previous_revenue: float
    change_units_pct: float
    change_revenue_pct: float
    trend: str  # "increase", "decrease", "stable"

class SalesAnalyticsResponse(BaseModel):
    total_revenue: float
    total_units: int
    daily_average_revenue: float
    time_window_days: int
    comparison_7d_vs_prev7d: Optional[PeriodSalesComparison] = None
    top_selling_products: List[Dict[str, Any]] = Field(default_factory=list)
    lowest_selling_products: List[Dict[str, Any]] = Field(default_factory=list)
    category_breakdown: List[Dict[str, Any]] = Field(default_factory=list)

class InventoryAnalyticsResponse(BaseModel):
    total_stock_units: int
    total_stock_value: float
    low_stock_items: List[ProductAnalyticsItem] = Field(default_factory=list)
    overstocked_items: List[ProductAnalyticsItem] = Field(default_factory=list)
    slow_moving_items: List[ProductAnalyticsItem] = Field(default_factory=list)

# ----------------- Chat Contracts -----------------
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
    evidence: Optional[EvidenceObject] = None
