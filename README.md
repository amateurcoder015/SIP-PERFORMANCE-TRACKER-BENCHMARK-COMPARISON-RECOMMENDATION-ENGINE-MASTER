# SIP Performance Tracker, Benchmark Comparison & Recommendation Engine

> [!IMPORTANT]
> **DISCLAIMER: NOT FINANCIAL ADVICE**
> This tool provides comparative analytics based on historical data for personal informational use only; it is not personalized investment advice; past performance does not guarantee future results.

---

## Overview

The **SIP Performance Tracker, Benchmark Comparison & Recommendation Engine** is a decision-support system designed for Indian mutual fund investors.

This tool aims to:
1. Ingest real Systematic Investment Plan (SIP) transaction histories.
2. Compute actual money-weighted returns (**XIRR**) per fund based on exact installment dates, contribution amounts, and current valuations.
3. Compute a fair, like-for-like **benchmark-equivalent XIRR** by simulating what the exact same SIP cashflows (same dates, same amounts) would have yielded if invested in benchmark indices (e.g. Nifty 50, Nifty Next 50, Nifty Midcap 100).
4. Recommend alternative funds in the same scheme category based on **long-term performance consistency**, risk-adjusted returns, and expense ratios.

---

## Project Roadmap

- [x] **Step 1 (Core Math Engine — THIS RELEASE)**: XIRR calculation engine, CAGR / Rolling CAGR module, and cashflow benchmark replication logic. Pure mathematical calculations fully unit-tested against hand-verified cashflow examples.
- [ ] **Step 2 (Data Layer)**: Fetch mutual fund daily NAVs via `mfapi.in`, benchmark index historical prices via `yfinance`, and parse transaction CSVs.
- [ ] **Step 3 (Per-Fund Performance Engine)**: Orchestration layer computing actual XIRR vs benchmark-equivalent XIRR per fund.
- [ ] **Step 4 (Recommendation Engine)**: Multi-metric peer fund scoring and ranking based on rolling return consistency, expense ratio, and risk-adjusted metrics.
- [ ] **Step 5 (Dashboard & Visual UI)**: Interactive decision-support web UI with disclaimers across all viewports.

---

## Repository Structure (Step 1)

```
.
├── README.md                     # Project overview, roadmap, and disclaimers
├── requirements.txt              # Core math & test dependencies
├── src/
│   ├── __init__.py
│   ├── _validators.py            # Shared input structure & cashflow validators
│   ├── cagr.py                   # Point-to-point CAGR and rolling trailing CAGR
│   ├── cashflow_replication.py   # Benchmark cashflow replication simulation engine
│   └── xirr.py                   # Newton-Raphson XIRR solver with duplicate netting
└── tests/
    ├── test_cagr.py              # Unit tests for CAGR calculations
    ├── test_cashflow_replication.py # Hand-verified benchmark replication tests
    └── test_xirr.py              # Hand-verified analytical & multi-period XIRR tests
```

---

## Mathematical Formulation & Conventions

### 1. XIRR Sign Convention (CRITICAL)
- **SIP Installments (Outflows)**: Represented as **NEGATIVE** values (`< 0`).
- **Valuation / Redemptions (Inflows)**: Represented as **POSITIVE** values (`> 0`) dated as of the valuation date.
- **Equation**:
  $$\sum_{i=0}^{N} \frac{C_i}{(1 + r)^{\frac{d_i - d_0}{365.0}}} = 0$$

### 2. Compound Annual Growth Rate (CAGR)
- **Formula**:
  $$\text{CAGR} = \left( \frac{\text{End Value}}{\text{Begin Value}} \right)^{\frac{1}{\text{Years}}} - 1$$

### 3. Benchmark Cashflow Replication
- For each installment on date $d_i$ with contribution amount $A_i < 0$:
  $$\text{Units Purchased}_i = \frac{|A_i|}{\text{Benchmark NAV}(d_i)}$$
- On market holidays or non-trading dates, the algorithm selects the nearest available **prior** trading date's benchmark index level.
- Total accumulated units $U = \sum \text{Units Purchased}_i$.
- Final valuation date benchmark cashflow:
  $$\text{Valuation Amount} = U \times \text{Benchmark NAV}(d_{\text{valuation}})$$

---

## Installation & Running Tests

### Setup Environment
```bash
pip install -r requirements.txt
```

### Running Test Suite
```bash
python3 -m pytest -v
```

---

## License & Disclaimer
This repository is for personal decision support and educational reference only. It does not constitute investment advice. Past performance does not guarantee future results.
