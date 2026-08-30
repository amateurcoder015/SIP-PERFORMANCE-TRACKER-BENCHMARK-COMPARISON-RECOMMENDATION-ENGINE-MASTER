"""
Unit tests for src/cashflow_replication.py module.

Includes hand-calculated benchmark replication tests, date matching checks, and edge case validation.
"""

from datetime import date
import pytest

from src.cashflow_replication import replicate_cashflows_in_benchmark
from src.xirr import calculate_xirr


def test_replicate_cashflows_hand_verified():
    """
    Hand-verified Test Case: Benchmark Replication Math & Unit Accumulation.

    ARITHMETIC DERIVATION:
    ----------------------
    Fund Cashflows (SIP installments + valuation):
      - 2023-01-01: -1000.0 (SIP Installment 1)
      - 2023-02-01: -1000.0 (SIP Installment 2)
      - 2023-03-01: +2100.0 (Valuation Date)

    Benchmark Index Levels:
      - 2023-01-01: 100.0
      - 2023-02-01: 125.0
      - 2023-03-01: 150.0

    Step 1: Installment 1 (2023-01-01)
      - Amount: -1000.0
      - Benchmark Index: 100.0
      - Benchmark Units Purchased: 1000.0 / 100.0 = 10.0 units

    Step 2: Installment 2 (2023-02-01)
      - Amount: -1000.0
      - Benchmark Index: 125.0
      - Benchmark Units Purchased: 1000.0 / 125.0 = 8.0 units

    Step 3: Total Notional Benchmark Units Accumulated
      - Total Units = 10.0 + 8.0 = 18.0 units

    Step 4: Valuation Date (2023-03-01)
      - Benchmark Index Level: 150.0
      - Benchmark Notional Value = 18.0 * 150.0 = 2700.0

    EXPECTED REPLICATED CASHFLOWS:
      - 2023-01-01: -1000.0
      - 2023-02-01: -1000.0
      - 2023-03-01: +2700.0
    """
    fund_cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2023, 2, 1), -1000.0),
        (date(2023, 3, 1), 2100.0),
    ]

    benchmark_nav = [
        (date(2023, 1, 1), 100.0),
        (date(2023, 2, 1), 125.0),
        (date(2023, 3, 1), 150.0),
    ]

    replicated = replicate_cashflows_in_benchmark(fund_cashflows, benchmark_nav)

    assert len(replicated) == 3
    assert replicated[0] == (date(2023, 1, 1), -1000.0)
    assert replicated[1] == (date(2023, 2, 1), -1000.0)
    assert replicated[2][0] == date(2023, 3, 1)
    assert pytest.approx(replicated[2][1], abs=1e-6) == 2700.0

    # Cross-check: benchmark XIRR on replicated cashflows
    bm_xirr = calculate_xirr(replicated)
    assert bm_xirr > 0.0


def test_replicate_cashflows_nearest_prior_trading_date():
    """
    Verify nearest prior trading date matching when cashflow date is on a weekend/holiday.

    ARITHMETIC DERIVATION:
    ----------------------
    - Fund cashflow date: Sunday 2023-01-08 (-1000.0)
    - Benchmark dates available:
        Friday 2023-01-06 (Index = 100.0)
        Monday 2023-01-09 (Index = 110.0)
    - According to rule: Select nearest available PRIOR trading date (2023-01-06, NAV 100.0).
    - Units bought = 1000.0 / 100.0 = 10.0 units.
    - Final valuation date: 2023-01-15 (NAV prior is 2023-01-13 = 120.0).
    - Final valuation = 10.0 * 120.0 = 1200.0.
    """
    fund_cashflows = [
        (date(2023, 1, 8), -1000.0),
        (date(2023, 1, 15), 1100.0),
    ]

    benchmark_nav = [
        (date(2023, 1, 6), 100.0),  # Friday
        (date(2023, 1, 9), 110.0),  # Monday
        (date(2023, 1, 13), 120.0), # Friday
        (date(2023, 1, 16), 125.0), # Monday
    ]

    replicated = replicate_cashflows_in_benchmark(fund_cashflows, benchmark_nav)

    assert len(replicated) == 2
    assert replicated[0] == (date(2023, 1, 8), -1000.0)
    assert replicated[1][0] == date(2023, 1, 15)
    assert pytest.approx(replicated[1][1], abs=1e-6) == 1200.0


def test_replicate_cashflows_benchmark_coverage_error():
    """Verify ValueError when benchmark series starts later than first fund cashflow date."""
    fund_cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2023, 2, 1), 1100.0),
    ]

    # Benchmark starts on 2023-01-05 (later than 2023-01-01)
    benchmark_nav = [
        (date(2023, 1, 5), 100.0),
        (date(2023, 2, 1), 110.0),
    ]

    with pytest.raises(ValueError, match="Benchmark NAV series starts on 2023-01-05, which is later than"):
        replicate_cashflows_in_benchmark(fund_cashflows, benchmark_nav)


def test_replicate_cashflows_intermediate_positive_error():
    """Verify ValueError when an intermediate cashflow is non-negative."""
    fund_cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2023, 2, 1), 500.0),  # Intermediate positive amount
        (date(2023, 3, 1), 1100.0),
    ]

    benchmark_nav = [
        (date(2023, 1, 1), 100.0),
        (date(2023, 2, 1), 105.0),
        (date(2023, 3, 1), 110.0),
    ]

    with pytest.raises(ValueError, match="Intermediate cashflow at index 1 on date 2023-02-01 is non-negative"):
        replicate_cashflows_in_benchmark(fund_cashflows, benchmark_nav)
