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

## Core Features
- **Deterministic Analytics Engine**: Computes exact run-rates, days of supply ($\frac{\text{Current Stock}}{\text{Average Daily Sales}}$), and velocity shifts in pure Python and SQLite.
- **Configurable Thresholds**: Live manager tuning of safety stock day buffers, overstock limits, and spike multipliers via the UI.
- **Grounded GenAI Copilot**: Gemini interprets queries and reasons over structured Python calculations without hallucinating statistics. Seamless local fallback engine if `GEMINI_API_KEY` is not set or network is offline.
- **Attention Required Command Center**: High-visibility operational alert feed categorizing issues into `URGENT`, `WARNING`, and `OPPORTUNITY`.
- **Interactive Multi-Store Dashboard**: Real-time KPI summary cards, 30-day sales trajectory line charts, top revenue generators, stock level buffers, and category share of wallet using Chart.js.
- **Full Inventory Matrix**: Searchable catalogue with SKU-level velocity, days of stock, and automated health classification.

---

## Architecture

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                      Frontend Client                        │
 │    Single-Page Web Application (HTML5, Vanilla CSS, JS)     │
 │    Chart.js Visualizations & Natural Language Chat UI       │
 └──────────────────────────────┬──────────────────────────────┘
                                │ HTTP / REST (Port 8000)
 ┌──────────────────────────────▼──────────────────────────────┐
 │                    FastAPI Backend (app.py)                 │
 ├─────────────────────────────────────────────────────────────┤
 │  • Static Asset Mount (`/static`, `/`)                      │
 │  • REST Endpoints (`/api/dashboard`, `/api/alerts`, etc.)   │
 │  • Copilot Query Pipeline (`/api/chat`)                     │
 └──────────────┬──────────────────────────────┬───────────────┘
                │                              │
 ┌──────────────▼─────────────┐ ┌──────────────▼───────────────┐
 │   Deterministic Analytics  │ │     Grounded Gemini AI      │
 │        (src/rules.py &     │ │   (src/gemini_service.py)   │
 │        src/analytics.py)   │ │  • Structured Prompting     │
 │  • Days of Supply          │ │  • Epistemic Honesty Rules  │
 │  • Stockout Detection      │ │  • Zero Hallucinations      │
 │  • Overstock & Slow-Moving │ │  • Offline Fallback Engine  │
 │  • Spikes & Drops          │ └──────────────┬───────────────┘
 └──────────────┬─────────────┘                │ GEMINI_API_KEY
                │                              │ (Only External API)
 ┌──────────────▼──────────────────────────────▼───────────────┐
 │                  Local SQLite Persistence                   │
 │                     (retail_copilot.db)                     │
 │      Stores  │  Products  │  Daily Sales  │  Inventory     │
 └─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack
- **Backend**: Python 3.11+ / 3.13, FastAPI, Uvicorn, pandas, SQLite, Pydantic
- **Frontend**: HTML5, Vanilla CSS (Modern Slate & Glassmorphism Design System), JavaScript (ES6+), Chart.js (CDN)
- **AI / LLM**: Google Gemini API via official `google-genai` SDK (`gemini-2.5-flash`)
- **Persistence**: Embedded SQLite (`retail_copilot.db`) populated from calibrated CSVs

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

## How Gemini is Used vs. Deterministic Python
| Responsibility | Engine | Implementation |
| :--- | :--- | :--- |
| Metric Calculations | **Python** | Days of stock, averages, velocity ratios, and thresholds are computed in Python (`src/rules.py`). Gemini is never allowed to calculate or guess numbers. |
| Intent Classification | **Python / Regex** | Maps questions to specific retail queries, product matches, and data windows. |
| Synthesis & Explanations | **Gemini AI** | Converts verified Python numbers into concise, executive summaries for the store manager. |
| Grounding & Evidence | **Python & Gemini** | Every response outputs a structured `data_used` block displaying exact inputs, timestamps, and filters. |
| Offline Continuity | **Python Engine** | If `GEMINI_API_KEY` is not provided or the network is unavailable, a deterministic response generator handles the query with identical numbers and zero disruption. |

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

### 3. (Optional) Configure Gemini API Key
To enable Gemini natural-language synthesis:
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your_actual_api_key_here"

# Windows (Command Prompt)
set GEMINI_API_KEY=your_actual_api_key_here

# Linux / macOS
export GEMINI_API_KEY="your_actual_api_key_here"
```
> **Note**: If `GEMINI_API_KEY` is not configured, the copilot will automatically use its built-in deterministic Python response generator with full numerical accuracy.

---

## Running the Application
Start the application with a single command:
```bash
python app.py
```
Open your browser and navigate to:
**[http://localhost:8000](http://localhost:8000)**

*No secondary terminal or separate frontend build command required.*

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
- **Interactive Browser Demonstration Recording**: Included in repo documentation.
- **API Documentation**: Available at `http://localhost:8000/docs`.
