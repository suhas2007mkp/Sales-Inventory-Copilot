"""
Gemini Service for Sales & Inventory Copilot (PS03)
Responsible strictly for Gemini API communication, structured prompt framing,
and response synthesis.
Never computes business calculations; strictly uses data provided by Python.
"""
import os
import json
from typing import Optional, Dict, Any
from src.utils import setup_logger, load_env_file

logger = setup_logger("gemini_service")
load_env_file()

def is_gemini_available() -> bool:
    """Checks if GEMINI_API_KEY is configured in the environment."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return bool(key)

def generate_grounded_response(
    question: str,
    calculation_data: Dict[str, Any],
    evidence: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Sends deterministic calculation results to Gemini for natural-language synthesis.
    Enforces strict grounding: LLM is barred from altering or inventing numbers.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Skipping Gemini call.")
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""You are the Sales & Inventory Copilot for a retail store manager.
Your task is to answer the manager's question using ONLY the provided structured calculation data.

MANAGER QUESTION: "{question}"

CALCULATED BUSINESS DATA (DETERMINISTIC FROM PYTHON & SQLITE):
{json.dumps(calculation_data, indent=2)}

EVIDENCE METADATA:
{json.dumps(evidence or {}, indent=2)}

STRICT GROUNDING RULES:
1. You MUST NOT calculate or alter any numbers. Cite only the exact metrics provided in the JSON above.
2. If insufficient_data is True, you MUST explicitly state that the available data does not contain enough information to determine why this occurred (as external factors like footfall, marketing, or competitor discounts are not recorded in the store database). Never guess causes.
3. Show the supporting numbers clearly (e.g. current stock, average daily sales, days of stock).
4. State the operational assumptions and recommended grounded actions (e.g. check shelf visibility, expiry dates).
5. Keep the answer professional, concise, and structured.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        if response and response.text:
            return response.text.strip()
        return None

    except Exception as e:
        logger.error(f"Gemini API communication failed: {e}")
        return None
