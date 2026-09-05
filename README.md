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
- [ ] **Step 5 (Dashboard & Visual UI)**: Interactive decision-support web UI with disclaimers across all viewports.

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
# Run all unit tests (offline)
python3 -m pytest -m "not integration" -v

# Run live integration tests (network access required)
python3 -m pytest -m integration -v -s
```

---

## License & Disclaimer
This repository is for personal decision support and educational reference only. It does not constitute investment advice. Past performance does not guarantee future results.
