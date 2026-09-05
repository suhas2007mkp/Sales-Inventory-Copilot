TRACK_ID=PS03
# Sales & Inventory Copilot (Retail Intelligence)

An intelligent copilot engineered for retail store managers operating single or multi-store footprints. The system couples **deterministic Python analytics** (zero hallucinations on business metrics) with **Gemini AI reasoning** to deliver grounded, actionable recommendations backed by real transaction data, mathematical assumptions, and operational evidence.

---

## Problem Statement
Store managers oversee thousands of SKUs across multiple locations with shifting customer footfall, supplier lead times, and promotional surges. Traditional retail software overwhelms managers with raw CSVs or static spreadsheets without actionable guidance.

**Sales & Inventory Copilot** solves this by:
1. Translating natural language queries into structured mathematical audits.
2. Flagging imminent stockouts before shelves run empty.
3. Identifying overstocked and slow-moving items to release trapped working capital.
4. Detecting abnormal demand spikes and sudden sales contractions.
5. Providing full transparency: every recommendation presents the **finding**, **supporting numbers**, **assumptions**, and **recommended action**.
6. Enforcing strict epistemic honesty: if available transactional data is insufficient to establish root cause, the copilot explicitly declares so instead of guessing.

---

## Clean Service-Layer Architecture

```text
app.py                              # FastAPI startup, route registration, static mounting
src/
├── database.py                     # Safe parameterized SQLite queries & indexes
├── models.py                       # Core domain entity dataclasses
├── schemas.py                      # Pydantic request/response & Evidence contracts
├── rules.py                        # Thread-safe configurable inventory & sales rules
├── analytics.py                    # Analytics facade coordinating modular services
├── sales_service.py                # Period comparisons, top/lowest sellers, volume & revenue
├── inventory_service.py            # Run-rates, stockout forecasting, turnover & reorder math
├── recommendation_service.py       # Deterministic business findings, evidence, assumptions, actions
├── chat_service.py                 # Natural-language intent routing & grounded orchestration
├── gemini_service.py               # Pure Gemini API communication (gemini-2.5-flash)
└── utils.py                        # Safe math division, date windows, logging, and env loading
tests/
└── test_backend.py                 # Automated unit and integration test suite (pytest)
```

---

## Tech Stack
- **Backend**: Python 3.11+ / 3.13, FastAPI, Uvicorn, pandas, SQLite, Pydantic, Pytest
- **Frontend**: HTML5, Vanilla CSS (Modern Slate & Glassmorphism Design System), JavaScript (ES6+), Chart.js (CDN)
- **AI / LLM**: Google Gemini API via official `google-genai` SDK (`gemini-2.5-flash`)
- **Persistence**: Embedded SQLite (`retail_copilot.db`) with parameterized queries and indexes

---

## Dataset Description (Realistic Indian Retail)
Located in [`data/`](file:///c:/Users/Lenovo/Downloads/ps3/data):
- **Stores (`stores.csv`)**: 3 physical retail hubs across Bengaluru:
  - `ST01`: Koramangala Flagship Superstore
  - `ST02`: Indiranagar Metro Express
  - `ST03`: Jayanagar Mega Mart
- **Products (`products.csv`)**: 20 fast-moving retail SKUs priced in Indian Rupees (₹) across Groceries & Staples, Snacks & Beverages, Personal Care, Electronics & Accessories, and Home & Kitchen.
- **Sales (`sales.csv`)**: 2,700 daily sales records spanning 45 days with weekend lifts and calibrated trends.
- **Inventory (`inventory.csv`)**: 60 store-level stock records engineered for deterministic demo scenarios:
  - *Likely Stock-Out*: Tata Tea Gold 500g (< 2.1 days supply), Portronics Type-C Cable (< 1.7 days supply).
  - *Overstocked*: Prestige Pressure Cooker 3L (> 200 days supply), Cadbury Dairy Milk Silk (> 120 days supply).
  - *Slow-Moving*: Havells Extension Board, Nivea Soft Cream (near-zero sales over 30 days).
  - *Sales Spike*: boAt Rockerz 255 Neckband (+400% 7-day surge).
  - *Sales Drop*: Dettol Liquid Handwash Refill (-91.3% 7-day decline).

---

## API Documentation & Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System health, track ID, and version |
| `GET` | `/api/dashboard` | Top-level KPI overview and active alert counts |
| `GET` | `/api/products` | Complete catalogue with velocity, days of stock, and health tags |
| `GET` | `/api/products/{product_id}` | Individual SKU detail, inventory, and specific alert history |
| `GET` | `/api/stores` | Store network listing |
| `GET` | `/api/sales` | Aggregate sales volume and revenue for time windows |
| `GET` | `/api/inventory` | Inventory valuation and stock health distribution |
| `GET` | `/api/alerts` | Prioritized operational alerts (Low stock, overstock, slow-moving) |
| `GET` | `/api/analytics/sales` | Period-over-period comparisons (Current 7d vs Prev 7d), top & lowest sellers |
| `GET` | `/api/analytics/inventory` | Forward-looking stockout projections and excess inventory analysis |
| `GET` | `/api/recommendations` | Deterministic action recommendations with evidence & assumptions |
| `GET` | `/api/config` | Returns active rule thresholds |
| `POST` | `/api/config` | Manager updates to thresholds (low stock days, overstock days, etc.) |
| `POST` | `/api/chat` | Natural-language query interface grounded with Gemini & deterministic fallback |

---

## How Gemini is Used vs. Deterministic Python
| Responsibility | Engine | Implementation |
| :--- | :--- | :--- |
| Metric Calculations | **Python** | Days of stock, averages, velocity ratios, and thresholds are computed in Python (`src/inventory_service.py`, `src/sales_service.py`). Gemini is never allowed to calculate or guess numbers. |
| Intent Classification | **Python / Regex** | Maps questions to specific retail queries, product matches, and data windows (`src/chat_service.py`). |
| Synthesis & Explanations | **Gemini AI** | Converts verified Python numbers into concise, executive summaries for the store manager (`src/gemini_service.py`). |
| Grounding & Evidence | **Python & Gemini** | Every response outputs a structured `evidence` object displaying exact data sources, formulas, and parameters. |
| Offline Continuity | **Python Engine** | If `GEMINI_API_KEY` is not provided or network is down, the built-in deterministic response generator produces full answers with identical numbers. |

---

## Installation & Setup

### Prerequisites
- Python 3.11 or higher
- Git

### 1. Clone & Enter Project
```bash
git clone https://github.com/suhas2007mkp/Sales-Inventory-Copilot.git
cd Sales-Inventory-Copilot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Gemini API Key
Configure your Gemini API key in your environment or local `.env` file (which is git-ignored):
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your_actual_api_key_here"

# Windows (Command Prompt)
set GEMINI_API_KEY=your_actual_api_key_here

# Linux / macOS
export GEMINI_API_KEY="your_actual_api_key_here"
```

---

## Running the Application
Start the application with a single command:
```bash
python app.py
```
Open your browser and navigate to:
**[http://localhost:8000](http://localhost:8000)**

---

## Running Backend Tests
Execute the complete automated test suite:
```bash
python -m pytest tests/test_backend.py -v
```
All 17 test cases validate rule calculations, period comparisons, stockout forecasts, and API contracts.

---

## Example Questions to Try in Copilot
- *"What products are running out?"*
- *"What products are overstocked?"*
- *"What needs attention today?"*
- *"Which product sold the most this month?"*
- *"How did boAt Rockerz 255 perform this month?"*
- *"Show me products with declining sales."*

---

## Difficult Demo Test Cases

### 1. Forward Stockout Forecast
> **Prompt**: *"Which product will run out next week?"*  
> **System Behavior**: The system calculates forward-looking run-rates ($$\text{current\_stock} / \text{avg\_daily\_sales\_7d} \le 7.0$$). It pinpoints Tata Tea Gold (2.1 days) and Portronics Cable (1.7 days) and explicitly documents the operational assumption that demand remains constant with zero supplier arrivals.

### 2. Epistemic Honesty (Unknown Root Cause)
> **Prompt**: *"Why did sales decrease for Dettol Handwash?"*  
> **System Behavior**: The system calculates the verified drop ($$13.07 \rightarrow 1.14$$ units/day, $$-91.3\%$$), but explicitly informs the manager:  
> *"The available transactional data shows a sales decrease, but it does not contain enough information to determine why (e.g., competitor promotions, local footfall drop, or distributor delays)."*  
> It then gives grounded operational check items (shelf placement, expiry, competitor price survey).

---

## Project Limitations
1. **Transaction Log Scope**: Does not track external web scraper feeds or live competitor prices.
2. **Static Lead Times**: Assumes standard supplier turnaround unless manually adjusted in safety stock buffers.

---

## Demo Video & Screenshots
- **Interactive Browser Demonstration Recording**: Included in repository artifacts (`copilot_dashboard_demo.webp`).
- **Interactive OpenAPI Documentation**: Available live at `http://localhost:8000/docs`.
