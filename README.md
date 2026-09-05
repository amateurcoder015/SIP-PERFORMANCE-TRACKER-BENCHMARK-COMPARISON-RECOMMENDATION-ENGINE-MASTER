# SIP Performance Tracker, Benchmark Comparison & Recommendation Engine

> [!IMPORTANT]
> **DISCLAIMER: NOT FINANCIAL ADVICE**
> This tool provides comparative analytics based on historical data for personal informational use only; it is not personalized investment advice; past performance does not guarantee future results.

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
- [x] **Step 3 (Per-Fund Performance Engine — THIS RELEASE)**: Single-fund and multi-fund performance orchestrators computing actual XIRR vs benchmark-equivalent XIRR and absolute alpha for identical cashflows.
- [ ] **Step 4 (Recommendation Engine)**: Multi-metric peer fund scoring and ranking based on rolling return consistency, expense ratio, and risk-adjusted metrics.
- [ ] **Step 5 (Dashboard & Visual UI)**: Interactive decision-support web UI with disclaimers across all viewports.

---

## Step 3 Performance Engine Specifications

### 1. Units & Current Value Calculation (`compute_units_and_current_value`)
- **Date Matching**: SIP transactions are matched against the fund's NAV on that exact date. If no exact match exists (weekend/market holiday), the nearest **PRIOR** available NAV date is used.
- **Mismatch Tolerance Flagging**: If the nearest prior NAV date differs from the transaction date by $> 5$ calendar days (default tolerance), a warning is flagged in `FundPerformanceResult.nav_date_mismatch_warnings`.
- **Valuation Date**: Defaults to the latest available NAV date in `FundNAVHistory`. If a `valuation_date` is requested that exceeds the latest available NAV date, a `ValueError` is raised.

### 2. Derived Cashflow Lists
- **Actual Investor Cashflows**: `[(date, -amount) for transactions] + [(effective_valuation_date, +current_value)]`. Evaluated via `calculate_xirr()` to compute `actual_xirr`.
- **Fund Cashflows for Benchmark Replication**: `[(date, -amount) for transactions] + [(effective_valuation_date, +current_value)]`. Replicated via `replicate_cashflows_in_benchmark()`, then evaluated via `calculate_xirr()` to compute `benchmark_xirr`.
- **Alpha**: $\text{Alpha} = \text{actual\_xirr} - \text{benchmark\_xirr}$.

### 3. Investor History Span Validation (`min_years_required`)
`validate_sufficient_history()` validates that the investor's **actual transaction window** ($T_{\text{first\_transaction}} \to T_{\text{effective\_valuation}}$) spans at least `min_years_required` (default 1.0 year).

### 4. Single-Fund vs. Multi-Fund Exception Handling
- **Single-Fund (`evaluate_fund_performance`)**: Propagates Step 1 and Step 2 validation errors directly (`ValueError` raised).
- **Multi-Fund Batch (`evaluate_all_funds`)**: Captures exceptions per scheme in `dict[str, FundPerformanceResult | Exception]` so one bad or short fund does not abort batch evaluation of other funds.

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
│   └── xirr.py                   # Newton-Raphson XIRR solver (Step 1)
└── tests/
    ├── fixtures/                 # Frozen API response fixtures from Step 0
    ├── test_cagr.py              # Unit tests for CAGR (Step 1)
    ├── test_cashflow_replication.py # Hand-verified benchmark replication tests (Step 1)
    ├── test_csv_parsing.py       # Unit tests for CSV parser (Step 2)
    ├── test_data_fetch.py        # Unit tests for data fetchers (Step 2)
    ├── test_integration_data_fetch.py # Live network integration test (Step 2)
    ├── test_performance_engine.py # Hand-verified performance engine tests (Step 3)
    └── test_xirr.py              # Hand-verified XIRR unit tests (Step 1)
```

---

## Running Tests

```bash
# Run all unit and integration tests
python3 -m pytest -v
```

---

## License & Disclaimer
This repository is for personal decision support and educational reference only. It does not constitute investment advice. Past performance does not guarantee future results.
