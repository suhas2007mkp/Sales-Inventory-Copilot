"""
Data models and typed domain entities for Sales & Inventory Copilot (PS03)
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class StoreModel:
    store_id: str
    store_name: str
    location: str

@dataclass
class ProductModel:
    product_id: str
    product_name: str
    category: str
    price: float
    supplier: str

@dataclass
class SaleModel:
    id: Optional[int]
    date: str
    store_id: str
    product_id: str
    quantity_sold: int
    revenue: float

@dataclass
class InventoryModel:
    id: Optional[int]
    date: str
    store_id: str
    product_id: str
    stock_quantity: int

@dataclass
class PeriodComparison:
    period_name: str
    current_period: str
    previous_period: str
    current_value: float
    previous_value: float
    absolute_change: float
    pct_change: float
    trend: str  # "increase", "decrease", "stable"
