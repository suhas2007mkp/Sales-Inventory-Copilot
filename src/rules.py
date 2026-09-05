"""
Deterministic Inventory & Sales Rules Configuration and Evaluation
Defines configurable thresholds and alert evaluation for retail operations.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class InventoryConfig(BaseModel):
    # Thresholds
    low_stock_days_threshold: float = Field(default=5.0, description="Days of stock below which likely stockout is flagged")
    critical_stock_days_threshold: float = Field(default=2.5, description="Days of stock below which urgent stockout is flagged")
    overstock_days_threshold: float = Field(default=45.0, description="Days of stock above which overstock is flagged")
    slow_moving_daily_sales: float = Field(default=0.15, description="Daily sales below which stagnant stock is flagged")
    slow_moving_min_stock: int = Field(default=20, description="Minimum units sitting idle required for slow-moving alert")
    spike_ratio_threshold: float = Field(default=1.7, description="Recent velocity ratio vs baseline triggering sales spike alert")
    drop_ratio_threshold: float = Field(default=0.5, description="Recent velocity ratio vs baseline triggering sales drop alert")
    
    # Analysis periods (in days)
    recent_period_days: int = 7
    historical_period_days: int = 30

# Thread-safe active configuration instance
_ACTIVE_CONFIG = InventoryConfig()

def get_active_config() -> InventoryConfig:
    """Returns the globally active inventory configuration."""
    return _ACTIVE_CONFIG

def set_active_config(updates: Dict[str, Any]) -> InventoryConfig:
    """Safely updates active thresholds."""
    global _ACTIVE_CONFIG
    current_dict = _ACTIVE_CONFIG.model_dump()
    for k, v in updates.items():
        if k in current_dict and v is not None:
            try:
                target_type = type(current_dict[k])
                current_dict[k] = target_type(v)
            except (ValueError, TypeError):
                pass
    _ACTIVE_CONFIG = InventoryConfig(**current_dict)
    return _ACTIVE_CONFIG

DEFAULT_CONFIG = _ACTIVE_CONFIG

def evaluate_low_stock(
    product_name: str,
    current_stock: int,
    avg_daily_sales: float,
    config: Optional[InventoryConfig] = None,
    store_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Evaluates if a product is running out or at risk of stock-out.
    Formula: days_of_stock = current_stock / avg_daily_sales
    """
    cfg = config or get_active_config()
    if avg_daily_sales <= 0:
        return None

    days_of_stock = round(current_stock / avg_daily_sales, 1)

    if days_of_stock < cfg.low_stock_days_threshold:
        is_critical = days_of_stock <= cfg.critical_stock_days_threshold
        severity = "URGENT" if is_critical else "WARNING"
        location_str = f" at {store_name}" if store_name else ""
        
        return {
            "finding": f"{product_name}{location_str} is at risk of stock-out with only {days_of_stock} days of supply remaining.",
            "alert_type": "LOW_STOCK",
            "severity": severity,
            "supporting_numbers": {
                "current_stock": current_stock,
                "avg_daily_sales": round(avg_daily_sales, 2),
                "days_of_stock": days_of_stock,
                "threshold": cfg.low_stock_days_threshold
            },
            "assumption": f"Sales velocity over the last {cfg.recent_period_days} days ({round(avg_daily_sales, 2)} units/day) will continue at current demand levels without lead-time delay.",
            "recommended_action": f"Initiate replenishment purchase order immediately for {max(30, int(avg_daily_sales * 21))} units to cover 3 weeks of safety stock."
        }
    return None

def evaluate_overstock(
    product_name: str,
    current_stock: int,
    avg_daily_sales: float,
    config: Optional[InventoryConfig] = None,
    store_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Evaluates if a product is significantly overstocked relative to run rate.
    """
    cfg = config or get_active_config()
    if current_stock < cfg.slow_moving_min_stock:
        return None

    if avg_daily_sales <= 0.05:
        days_of_stock = 999.0
    else:
        days_of_stock = round(current_stock / avg_daily_sales, 1)

    if days_of_stock > cfg.overstock_days_threshold:
        location_str = f" at {store_name}" if store_name else ""
        days_str = f"{days_of_stock} days" if days_of_stock < 999 else "> 300 days (near zero velocity)"
        
        return {
            "finding": f"{product_name}{location_str} is overstocked with {current_stock} units ({days_str} of inventory).",
            "alert_type": "OVERSTOCK",
            "severity": "WARNING",
            "supporting_numbers": {
                "current_stock": current_stock,
                "avg_daily_sales": round(avg_daily_sales, 2),
                "days_of_stock": days_of_stock if days_of_stock < 999 else None,
                "threshold": cfg.overstock_days_threshold
            },
            "assumption": f"Current low consumption rate ({round(avg_daily_sales, 2)} units/day) causes working capital blockage and risk of shelf-life or obsolescence costs.",
            "recommended_action": "Halt new purchase orders, initiate a bundled promotional discount, or reallocate excess inventory to high-velocity stores."
        }
    return None

def evaluate_slow_moving(
    product_name: str,
    current_stock: int,
    historical_daily_sales: float,
    total_units_sold_30d: int,
    config: Optional[InventoryConfig] = None,
    store_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Identifies products with negligible sales over 30 days while holding notable stock.
    """
    cfg = config or get_active_config()
    if current_stock >= cfg.slow_moving_min_stock and historical_daily_sales <= cfg.slow_moving_daily_sales:
        location_str = f" at {store_name}" if store_name else ""
        return {
            "finding": f"{product_name}{location_str} is stagnant/slow-moving: only {total_units_sold_30d} units sold in past 30 days with {current_stock} units idle in stock.",
            "alert_type": "SLOW_MOVING",
            "severity": "WARNING",
            "supporting_numbers": {
                "current_stock": current_stock,
                "units_sold_recent": total_units_sold_30d,
                "avg_daily_sales": round(historical_daily_sales, 2),
                "threshold": cfg.slow_moving_daily_sales
            },
            "assumption": "Consumer interest is minimal at current shelf placement and price point, leading to dead capital.",
            "recommended_action": "Review retail pricing, offer an introductory 15% discount, or move product to prominent eye-level display."
        }
    return None

def evaluate_sales_spike(
    product_name: str,
    recent_daily_sales: float,
    historical_daily_sales: float,
    current_stock: int,
    config: Optional[InventoryConfig] = None,
    store_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Identifies abnormal upward spike in sales velocity compared to historical baseline.
    """
    cfg = config or get_active_config()
    if historical_daily_sales <= 0.2:
        return None

    ratio = recent_daily_sales / historical_daily_sales
    if ratio >= cfg.spike_ratio_threshold:
        pct_increase = round((ratio - 1.0) * 100, 1)
        location_str = f" at {store_name}" if store_name else ""
        return {
            "finding": f"{product_name}{location_str} experienced a sales spike (+{pct_increase}%): recent velocity {round(recent_daily_sales, 2)} units/day vs {round(historical_daily_sales, 2)} historical.",
            "alert_type": "SALES_SPIKE",
            "severity": "OPPORTUNITY",
            "supporting_numbers": {
                "current_stock": current_stock,
                "recent_avg_daily_sales": round(recent_daily_sales, 2),
                "historical_avg_daily_sales": round(historical_daily_sales, 2),
                "sales_change_pct": pct_increase,
                "threshold": cfg.spike_ratio_threshold
            },
            "assumption": "Recent demand surge may be driven by promotional traction, viral trend, or seasonal rush; high risk of premature stockout if not monitored.",
            "recommended_action": "Audit supplier lead times, ensure safety stock is buffer-stocked, and assess if higher shelf capacity is required."
        }
    return None

def evaluate_sales_drop(
    product_name: str,
    recent_daily_sales: float,
    historical_daily_sales: float,
    current_stock: int,
    config: Optional[InventoryConfig] = None,
    store_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Identifies sudden drop in sales velocity compared to historical baseline.
    """
    cfg = config or get_active_config()
    if historical_daily_sales <= 0.5:
        return None

    ratio = recent_daily_sales / historical_daily_sales
    if ratio <= cfg.drop_ratio_threshold:
        pct_drop = round((1.0 - ratio) * 100, 1)
        location_str = f" at {store_name}" if store_name else ""
        return {
            "finding": f"{product_name}{location_str} had a sharp sales drop (-{pct_drop}%): recent velocity fell to {round(recent_daily_sales, 2)} units/day from {round(historical_daily_sales, 2)} historical.",
            "alert_type": "SALES_DROP",
            "severity": "WARNING",
            "supporting_numbers": {
                "current_stock": current_stock,
                "recent_avg_daily_sales": round(recent_daily_sales, 2),
                "historical_avg_daily_sales": round(historical_daily_sales, 2),
                "sales_change_pct": -pct_drop,
                "threshold": cfg.drop_ratio_threshold
            },
            "assumption": "Product demand fell sharply due to potential competitor discounting, stock visibility issue, or shifting customer preference.",
            "recommended_action": "Verify in-store shelf placement and expiry dates; survey competitor pricing; consider promotional discount."
        }
    return None
