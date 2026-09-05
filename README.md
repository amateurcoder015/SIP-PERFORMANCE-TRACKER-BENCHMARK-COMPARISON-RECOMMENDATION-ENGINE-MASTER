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
- [x] **Step 2 (Data Layer — THIS RELEASE)**: Real mutual fund NAV and scheme metadata fetcher via `mfapi.in`, real benchmark index fetcher via `yfinance`, and CSV transaction parser with zero live-network dependency in unit tests.
- [ ] **Step 3 (Per-Fund Performance Engine)**: Orchestration layer computing actual XIRR vs benchmark-equivalent XIRR per fund.
- [ ] **Step 4 (Recommendation Engine)**: Multi-metric peer fund scoring and ranking based on rolling return consistency, expense ratio, and risk-adjusted metrics.
- [ ] **Step 5 (Dashboard & Visual UI)**: Interactive decision-support web UI with disclaimers across all viewports.

---

## Step 2 Data Layer Specifications & Empirical Findings

### 1. Data Source Endpoints & Fields (`mfapi.in`)
- **Detail Endpoint**: `https://api.mfapi.in/mf/{scheme_code}`
  - Top-level JSON keys: `meta`, `data`, `status`.
  - `meta` fields: `scheme_code` (int), `scheme_name` (str), `fund_house` (str), `scheme_category` (str), `scheme_type` (str).
  - `data` array entries: `{'date': 'DD-MM-YYYY', 'nav': '90.52890'}`.
  - **Expense Ratio**: `mfapi.in` metadata does not supply expense ratios. Documented as a known API limitation rather than fabricating mock values.
- **Scheme List Summary Endpoint**: `https://api.mfapi.in/mf`
  - Returns array of ~37,800 scheme objects. Keys: `schemeCode`, `schemeName`, `isinGrowth`, `isinDivReinvestment`.
  - Category information is **not** present at the scheme list summary level (only in detail endpoints).

### 2. Ordering & Sign Conventions
- **Ascending Date Ordering**: `mfapi.in` delivers historical NAV points in **descending** order (newest first). `FundNAVHistory` and `BenchmarkSeries` explicitly sort and normalize all NAV series into **ASCENDING** order (`oldest -> newest`) to meet Step 1 core math requirements.
- **Positive Transaction Amounts**: `ParsedSIPTransaction.amount` stores contribution amounts as **POSITIVE** numbers (`> 0`) representing uncorrupted user CSV inputs. The negative sign flip (`< 0`) required by `calculate_xirr()` is performed at cashflow assembly in Step 3.

### 3. Benchmark Index Coverage & Gaps (`yfinance`)
- **Confirmed Working Tickers**:
  - `NIFTY50`: `^NSEI` (Nifty 50 Index)
  - `SENSEX`: `^BSESN` (S&P BSE Sensex Index)
  - `NIFTYMIDCAP`: `^NSMIDCP` (Nifty Midcap 100 Index)
  - `NIFTYBANK`: `^NSEBANK` (Nifty Bank Index)
- **Known Coverage Gap (Nifty Next 50)**: `yfinance` does not carry a working ticker for Nifty Next 50 (tickers like `^NIFTYNEXT50` and `^CNXNIFTY` return HTTP 404 / Quote not found). Requesting `"NIFTYNEXT50"` raises a clear `ValueError` naming unsupported benchmarks.
- **Price Field Choice**: `Close` is used as index levels do not undergo dividend or corporate action adjustments.

### 4. Scheme Category Granularity Finding
`mfapi.in` `scheme_category` fields use standardized strings such as `'Equity Scheme - Flexi Cap Fund'`, `'Equity Scheme - Mid Cap Fund'`, `'Equity Schemes - ELSS- Tax Saver Fund'`. Extracting core category keywords (e.g., `"Flexi Cap"`, `"Mid Cap"`, `"ELSS"`) provides clean category grouping for Step 4 peer recommendations.

---

## Repository Structure

```
.
├── README.md                     # Project overview, roadmap, and data layer specifications
├── requirements.txt              # Core math, data, & test dependencies
├── src/
│   ├── __init__.py
│   ├── _validators.py            # Shared input structure & cashflow validators (Step 1)
│   ├── cagr.py                   # Point-to-point CAGR and rolling trailing CAGR (Step 1)
│   ├── cashflow_replication.py   # Benchmark cashflow replication simulation engine (Step 1)
│   ├── data_fetch.py             # Data models, CSV parser, MF NAV & benchmark fetchers (Step 2)
│   └── xirr.py                   # Newton-Raphson XIRR solver (Step 1)
└── tests/
    ├── fixtures/                 # Frozen API JSON/CSV response fixtures from Step 0
    │   ├── benchmark_nifty50_sample.csv
    │   ├── mfapi_scheme_120503.json
    │   ├── mfapi_scheme_120505.json
    │   ├── mfapi_scheme_122639.json
    │   └── mfapi_scheme_list_sample.json
    ├── test_cagr.py              # Unit tests for CAGR (Step 1)
    ├── test_cashflow_replication.py # Hand-verified benchmark replication tests (Step 1)
    ├── test_csv_parsing.py       # Unit tests for CSV parser (Step 2)
    ├── test_data_fetch.py        # Fixture-based unit tests for data fetchers (Step 2)
    ├── test_integration_data_fetch.py # Live network integration test (Step 2)
    └── test_xirr.py              # Hand-verified XIRR unit tests (Step 1)
```

---

## Running Tests

### 1. Offline Unit Test Suite (Default)
Executes all Step 1 math unit tests, fixture-based data layer tests, and CSV parser tests without live network calls:
```bash
python3 -m pytest -m "not integration" -v
```

### 2. Live Integration Test
Executes real network requests against `mfapi.in` and `yfinance`:
```bash
python3 -m pytest tests/test_integration_data_fetch.py -v
```

---

## License & Disclaimer
This repository is for personal decision support and educational reference only. It does not constitute investment advice. Past performance does not guarantee future results.
