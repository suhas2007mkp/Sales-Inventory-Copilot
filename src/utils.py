"""
Utility functions for Sales & Inventory Copilot (PS03)
Provides safe mathematical operations, date computations, logging configuration,
and environment loading.
"""
import os
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

def load_env_file():
    """Safely loads key-value pairs from .env if present into os.environ without overriding existing vars."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass

# Load env variables automatically
load_env_file()

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division preventing ZeroDivisionError."""
    try:
        if denominator is None or denominator == 0:
            return default
        return numerator / denominator
    except (ZeroDivisionError, TypeError):
        return default

def calc_pct_change(current: float, previous: float) -> float:
    """Calculates percentage change between current and previous values."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100.0, 2)

def get_date_range(end_date_str: str, days: int) -> Tuple[str, str]:
    """Returns (start_date, end_date) strings in YYYY-MM-DD format for a given window."""
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=days - 1)
    return start_dt.strftime("%Y-%m-%d"), end_date_str

def get_comparison_windows(end_date_str: str, window_days: int) -> Tuple[str, str, str, str]:
    """
    Returns (curr_start, curr_end, prev_start, prev_end)
    for period-over-period comparison (e.g. Current 7d vs Previous 7d).
    """
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
    curr_start_dt = end_dt - timedelta(days=window_days - 1)
    prev_end_dt = curr_start_dt - timedelta(days=1)
    prev_start_dt = prev_end_dt - timedelta(days=window_days - 1)

    return (
        curr_start_dt.strftime("%Y-%m-%d"),
        end_dt.strftime("%Y-%m-%d"),
        prev_start_dt.strftime("%Y-%m-%d"),
        prev_end_dt.strftime("%Y-%m-%d")
    )

def setup_logger(name: str) -> logging.Logger:
    """Configures structured application logger without leaking secrets."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
