# SIP Performance Tracker, Benchmark Comparison & Recommendation Engine

> [!IMPORTANT]
> **DISCLAIMER: NOT FINANCIAL ADVICE**
> This tool provides comparative analytics based on historical mutual fund daily NAV data for personal informational use only. It is not personalized investment, financial, or tax advice, and past performance does not guarantee future results.

---

## Overview

The **SIP Performance Tracker, Benchmark Comparison & Recommendation Engine** is a decision-support system designed for Indian mutual fund investors.

This tool:
1. Ingests real Systematic Investment Plan (SIP) transaction histories via CSV upload.
2. Computes actual money-weighted returns (**XIRR**) per fund based on exact installment dates, contribution amounts, and current valuations.
3. Computes a fair, like-for-like **benchmark-equivalent XIRR** by simulating what the exact same SIP cashflows (same dates, same amounts) would have yielded if invested in benchmark indices (e.g. Nifty 50, S&P BSE Sensex, Nifty Midcap 100).
4. Recommends alternative funds in the same scheme category based on **long-term performance consistency**, risk-adjusted returns, and expense ratios.

---

## Project Roadmap

- [x] **Step 1 (Core Math Engine)**: XIRR calculation engine, CAGR / Rolling CAGR module, and cashflow benchmark replication logic. Pure mathematical calculations fully unit-tested against hand-verified cashflow examples.
- [x] **Step 2 (Data Layer)**: Real mutual fund NAV and scheme metadata fetcher via `mfapi.in`, real benchmark index fetcher via `yfinance`, and CSV transaction parser with zero live-network dependency in unit tests.
- [x] **Step 3 (Per-Fund Performance Engine)**: Single-fund and multi-fund performance orchestrators computing actual XIRR vs benchmark-equivalent XIRR and absolute alpha for identical cashflows.
- [x] **Step 4 (Recommendation Engine — THIS RELEASE)**: Long-term-weighted peer discovery, category normalization, multi-window rolling CAGR scoring (50/30/20 composite model), plain-language rationale generator, and mandatory disclaimers.
- [x] **Step 5 (Dashboard & Visual UI — FINAL RELEASE)**: React + FastAPI Bento-style web dashboard with per-fund XIRR cards, benchmark comparisons, long-term peer recommendations, and non-bypassable financial disclaimers.

---

## Running the Application

### 1. Start the FastAPI Backend API
```bash
# Install Python requirements
pip install -r requirements.txt

# Start backend dev server (port 8000)
python3 -m uvicorn api.main:app --reload --port 8000
```

### 2. Start the React Bento Dashboard
```bash
# Navigate to frontend directory
cd frontend

# Install node dependencies
npm install

# Start Vite dev server (port 5173)
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Step 5 React + FastAPI Bento Dashboard Specifications

### 1. Architecture & Endpoint Contracts

- **`POST /api/upload-transactions`**: Accepts a `.csv` file upload, parses SIP transactions, and returns summary stats grouped by `scheme_code` before triggering slow API calls.
- **`POST /api/performance`**: Body: `transactions`, `benchmark_name` (`NIFTY50`, `SENSEX`, `NIFTYMIDCAP`, `NIFTYBANK`), `valuation_date` (optional), `min_years_required` (default 1.0). Evaluates per-fund performance with per-fund exception isolation.
- **`POST /api/recommend`**: Body: `target_scheme_code`, `max_candidates_to_confirm` (default 30), `top_n` (default 5), `min_years_required` (default 3.0). Returns long-term ranked shortlist with verbatim reasoning and mandatory disclaimer.

### 2. In-Process Short TTL NAV Cache
To optimize response times when users evaluate fund performance and subsequently click "Find Alternative Peer Recommendations", `api/main.py` implements a 5-minute ($300$-second) in-process TTL memory cache for scheme NAV history fetched from `mfapi.in`.

### 3. Portfolio Summary Limitation (Capital Sums Only)
The Portfolio Summary Bento Panel displays **simple capital sums ONLY**:
- $\text{Total Invested} = \sum \text{total\_invested}_i$
- $\text{Current Valuation} = \sum \text{current\_value}_i$
- $\text{Absolute Gain} = \text{Current Valuation} - \text{Total Invested}$

> [!IMPORTANT]
> The application explicitly does **NOT** compute or display any blended multi-fund XIRR/CAGR rate. Combining cashflows across different funds into a single rate represents new financial scope not supported by Step 3's per-fund engine.

### 4. Bento Grid Layout Breakdown
- **Upload & Setup Panel**: Drag-and-drop CSV dropzone, benchmark selector dropdown, optional valuation date picker, parse summary box, and execution button.
- **Portfolio Summary Panel**: Capital sum totals and gain/loss percentage.
- **Per-Fund Performance Grid**: Cards displaying actual XIRR, benchmark XIRR, alpha badge (Emerald positive / Rose negative), investment span, units held, NAV mismatch warnings, or fund-level error messages.
- **Recommendation Panel**: Displays target fund baseline score, top ranked peers, 3-year mean rolling CAGRs, consistency stdevs, verbatim rationale strings, skipped funds, and **the mandatory, non-bypassable financial advice disclaimer rendered prominently inside the card in golden-amber highlight**.
- **Metadata Panel**: Provenance details, active benchmark specs, and data retrieved timestamps.

---

## Step 4 Recommendation Engine Specifications

### 1. Two-Phase Peer Discovery Architecture
- **Phase (a) Cheap Pre-Filter**: Scans full scheme list summaries (~37,800 items in memory), matching candidate scheme names containing category keywords (e.g. `"Flexi Cap"`) AND option keywords (`"Direct"` and `"Growth"`). Narrows candidates to ~30–60 scheme codes instantly without network overhead.
- **Phase (b) Category Confirmation & Scoring**: Calls `fetch_fund_nav_history()` for up to `max_candidates_to_confirm` (default 30) pre-filtered candidates. Confirms actual `scheme_category` metadata matches the target fund's category, discarding non-matching categories.
- **Pre-Filter Limitations**: Phase (a) is a heuristic filter that may miss peer funds with unconventional scheme names, or include funds whose name matches but whose true confirmed category differs (which Phase (b) safely filters out).
- **Runtime Tradeoff**: Confirming 30 candidate funds requires 30 sequential API calls taking ~4–10 seconds.

### 2. Long-Term Composite Scoring Formula (50 / 30 / 20 Bounded Normalization)
For each candidate with $\ge 3$ years of NAV history, `score_fund_long_term()` computes rolling CAGRs across 3yr, 5yr, and 10yr windows, normalizing each component onto a bounded $[0.0, 1.0]$ scale before applying the $50\% / 30\% / 20\%$ weights:

1. **50% Return Component ($S_{\text{return}} \in [0.0, 1.0]$)**:
   - Raw signal: Weighted average of `mean_rolling_cagr` across usable windows ($w_{10\text{y}} = 0.50, w_{5\text{y}} = 0.35, w_{3\text{y}} = 0.15$).
   - Normalization: Scaled linearly from $0.0$ ($0\%$ CAGR floor) to $0.25$ ($25\%$ CAGR ceiling for top equity performance):
     $$S_{\text{return}} = \text{clip}\left(\frac{R_{\text{raw}}}{0.25}, 0.0, 1.0\right)$$

2. **30% Return Consistency Component ($S_{\text{consistency}} \in [0.0, 1.0]$)**:
   - Raw signal: Weighted average of `stdev_rolling_cagr` across usable windows.
   - Normalization: Lower rolling return variance yields higher consistency. Scaled linearly where $\sigma = 0.0$ yields $1.0$ (perfect consistency), and $\sigma \ge 0.15$ ($15\%$ volatility ceiling) yields $0.0$:
     $$S_{\text{consistency}} = \text{clip}\left(1.0 - \frac{\sigma_{\text{raw}}}{0.15}, 0.0, 1.0\right)$$

3. **20% Risk-Adjusted Component ($S_{\text{risk}} \in [0.0, 1.0]$)**:
   - Raw signal: Sharpe-like ratio on the longest usable window relative to risk-free rate $r_f = 0.05$ ($5.0\%$):
     $$\text{Sharpe}_{\text{raw}} = \frac{R_{\text{longest}} - 0.05}{\sigma_{\text{longest}} + 1\text{e}-4}$$
   - Normalization: Clipped to $[0.0, 3.0]$ to prevent zero-stdev ratio explosions, and scaled linearly from $0.0$ to $1.0$ ($\text{Sharpe} \ge 3.0$ ceiling):
     $$S_{\text{risk}} = \text{clip}\left(\frac{\text{Sharpe}_{\text{raw}}}{3.0}, 0.0, 1.0\right)$$

4. **Composite Score ($0.0 \le \text{Composite Score} \le 1.0$)**:
   $$\text{Composite Score} = 0.50 \times S_{\text{return}} + 0.30 \times S_{\text{consistency}} + 0.20 \times S_{\text{risk}}$$
   This guarantees that `composite_score` lives on an interpretable $[0.0, 1.0]$ scale (or $0\% - 100\%$), preventing any single component from exceeding its stated weight share regardless of how extreme raw metrics are.

### 3. Expense Ratio Signal (`expense_ratio_considered = False`)
Because `mfapi.in` does not supply expense ratio metadata, `FundScore.expense_ratio_considered` is explicitly set to `False`. The 50/30/20 composite weighting formula accounts for its absence without fabricating mock proxy values.

### 4. Mandatory Disclaimer Enforcement
Every `RecommendationResult` object explicitly includes the mandatory financial advice disclaimer:
> `DISCLAIMER: NOT FINANCIAL ADVICE. This tool provides comparative analytics based on historical mutual fund daily NAV data for personal informational use only. It is not personalized investment, financial, or tax advice, and past performance does not guarantee future results.`

---

## Repository Structure

```
.
├── README.md                     # Project overview, roadmap, and specifications
├── pytest.ini                    # Pytest configuration
├── requirements.txt              # Project dependencies
├── api/
│   ├── __init__.py
│   ├── main.py                   # FastAPI backend endpoints, CORS & TTL cache
│   └── test_main.py              # Backend API unit tests (TestClient)
├── frontend/
│   ├── index.html
│   ├── package.json              # React + Vite + TypeScript + Tailwind CSS dependencies
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx               # Bento Grid Dashboard layout
│       ├── main.tsx
│       ├── types.ts              # TypeScript API data structures
│       ├── api.ts                # Fetch client for FastAPI endpoints
│       ├── index.css             # Tailwind & Glassmorphism styles
│       ├── utils/formatters.ts   # INR currency & percentage formatters
│       ├── components/           # Bento Card components
│       └── __tests__/            # Vitest frontend unit tests
├── src/
│   ├── __init__.py
│   ├── _validators.py            # Shared validators & validate_sufficient_history (Step 1+2)
│   ├── cagr.py                   # Point-to-point CAGR and rolling trailing CAGR (Step 1)
│   ├── cashflow_replication.py   # Benchmark cashflow replication engine (Step 1)
│   ├── data_fetch.py             # Data models, CSV parser, MF NAV & benchmark fetchers (Step 2)
│   ├── performance_engine.py     # Per-fund performance orchestrator & alpha engine (Step 3)
│   ├── recommendation_engine.py  # Peer discovery, long-term scoring & recommendation (Step 4)
│   └── xirr.py                   # Newton-Raphson XIRR solver (Step 1)
└── tests/
    ├── fixtures/                 # Frozen API response fixtures from Step 0
    ├── test_cagr.py              # Unit tests for CAGR (Step 1)
    ├── test_cashflow_replication.py # Hand-verified benchmark replication tests (Step 1)
    ├── test_csv_parsing.py       # Unit tests for CSV parser (Step 2)
    ├── test_data_fetch.py        # Unit tests for data fetchers (Step 2)
    ├── test_integration_data_fetch.py # Live network integration test for data layer (Step 2)
    ├── test_performance_engine.py # Hand-verified performance engine tests (Step 3)
    ├── test_recommendation_engine.py # Unit & integration tests for recommendation engine (Step 4)
    └── test_xirr.py              # Hand-verified XIRR unit tests (Step 1)
```

---

## Running Tests

```bash
# Run all Python backend unit & API tests (48 tests)
python3 -m pytest -v

# Run frontend React component unit tests (Vitest - 6 tests)
cd frontend && npm test
```

---

## License & Disclaimer
This repository is for personal decision support and educational reference only. It does not constitute investment advice. Past performance does not guarantee future results.

