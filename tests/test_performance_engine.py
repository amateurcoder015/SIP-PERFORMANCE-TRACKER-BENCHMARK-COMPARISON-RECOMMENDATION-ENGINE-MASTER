"""
Unit tests for src/performance_engine.py module.

Includes synthetic hand-verified mathematical proofs, date mismatch warning checks,
error propagations, and multi-fund exception isolation tests.
"""

from datetime import date, timedelta
import pytest

from src.data_fetch import BenchmarkSeries, FundMetadata, FundNAVHistory, ParsedSIPTransaction
from src.performance_engine import (
    compute_units_and_current_value,
    evaluate_all_funds,
    evaluate_fund_performance,
    FundPerformanceResult,
)


def test_evaluate_fund_performance_hand_verified():
    """
    Hand-verified Test Case: Single-fund performance orchestration & alpha math.

    SYNTHETIC DATA SETUP & ARITHMETIC PROOF:
    -----------------------------------------
    1. Scheme: Code "100001" ("Alpha Growth Fund")
       Benchmark: "NIFTY50"

    2. Fund NAV Series:
       2022-01-01 (day 0):   NAV = 100.0
       2022-07-01 (day 181): NAV = 110.0
       2023-01-01 (day 365): NAV = 120.0 (Valuation Date)

    3. Benchmark Index Series:
       2022-01-01 (day 0):   Level = 100.0
       2022-07-01 (day 181): Level = 105.0
       2023-01-01 (day 365): Level = 110.0

    4. Parsed SIP Transactions:
       - 2022-01-01: amount = 1000.0
       - 2022-07-01: amount = 1100.0

    5. Hand Calculation Steps:
       - Installment 1 (2022-01-01): NAV = 100.0 -> Units = 1000 / 100 = 10.0 units
       - Installment 2 (2022-07-01): NAV = 110.0 -> Units = 1100 / 110 = 10.0 units
       - Total Units Held = 10.0 + 10.0 = 20.0 units
       - Total Invested = 1000 + 1100 = 2100.0
       - Valuation (2023-01-01): NAV = 120.0 -> Current Value = 20.0 * 120.0 = 2400.0
       - Absolute Gain = 2400.0 - 2100.0 = 300.0

       - Actual Cashflows: [(2022-01-01, -1000.0), (2022-07-01, -1100.0), (2023-01-01, 2400.0)]
         Solving -1000 - 1100/(1+r)^(181/365) + 2400/(1+r)^(365/365) = 0
         Root r_actual = 0.19608969 (19.608969%)

       - Benchmark Cashflow Replication:
         - Installment 1 (2022-01-01): 1000 / 100.0 = 10.0 BM units
         - Installment 2 (2022-07-01): 1100 / 105.0 = 10.476190 BM units
         - Total BM Units = 20.476190 units
         - BM Valuation (2023-01-01): 20.476190 * 110.0 = 2252.380952
       - Replicated BM Cashflows: [(2022-01-01, -1000.0), (2022-07-01, -1100.0), (2023-01-01, 2252.380952)]
         Solving -1000 - 1100/(1+r_bm)^(181/365) + 2252.380952/(1+r_bm)^(365/365) = 0
         Root r_bm = 0.09884847 (9.884847%)

       - Alpha = r_actual - r_bm = 0.19608969 - 0.09884847 = 0.09724122 (9.724122%)
    """
    meta = FundMetadata(
        scheme_code=100001,
        scheme_name="Alpha Growth Fund",
        fund_house="Alpha MF",
        scheme_category="Equity Scheme - Large Cap Fund",
        scheme_type="Open Ended",
        data_retrieved_at="2023-01-01T00:00:00Z",
    )

    # 1. Construct valid FundNAVHistory spanning 1.5 years for density validation
    nav_dates = [date(2022, 1, 1) + timedelta(days=i) for i in range(366)]
    nav_points = []
    for dt in nav_dates:
        if dt == date(2022, 1, 1):
            nav_points.append((dt, 100.0))
        elif dt == date(2022, 7, 1):
            nav_points.append((dt, 110.0))
        elif dt == date(2023, 1, 1):
            nav_points.append((dt, 120.0))
        else:
            frac = (dt - date(2022, 1, 1)).days / 365.0
            nav_points.append((dt, 100.0 + 20.0 * frac))

    nav_history = FundNAVHistory(metadata=meta, nav_series=nav_points)

    # 2. Construct BenchmarkSeries
    bm_points = []
    for dt in nav_dates:
        if dt == date(2022, 1, 1):
            bm_points.append((dt, 100.0))
        elif dt == date(2022, 7, 1):
            bm_points.append((dt, 105.0))
        elif dt == date(2023, 1, 1):
            bm_points.append((dt, 110.0))
        else:
            frac = (dt - date(2022, 1, 1)).days / 365.0
            bm_points.append((dt, 100.0 + 10.0 * frac))

    benchmark_series = BenchmarkSeries(
        benchmark_name="NIFTY50",
        ticker="^NSEI",
        level_series=bm_points,
        data_retrieved_at="2023-01-01T00:00:00Z",
    )

    # 3. Parsed Transactions
    txs = [
        ParsedSIPTransaction(date=date(2022, 1, 1), scheme_code="100001", scheme_name="Alpha Growth Fund", amount=1000.0),
        ParsedSIPTransaction(date=date(2022, 7, 1), scheme_code="100001", scheme_name="Alpha Growth Fund", amount=1100.0),
    ]

    result = evaluate_fund_performance(
        transactions=txs,
        nav_history=nav_history,
        benchmark_series=benchmark_series,
        valuation_date=date(2023, 1, 1),
        min_years_required=1.0,
    )

    assert isinstance(result, FundPerformanceResult)
    assert result.scheme_code == "100001"
    assert result.total_invested == 2100.0
    assert result.units_held == 20.0
    assert result.current_value == 2400.0
    assert result.absolute_gain == 300.0
    assert result.num_transactions == 2

    # Verify hand-calculated XIRR and Alpha figures
    assert pytest.approx(result.actual_xirr, abs=1e-5) == 0.196090
    assert pytest.approx(result.benchmark_xirr, abs=1e-5) == 0.098848
    assert pytest.approx(result.alpha, abs=1e-5) == 0.097241


def test_date_mismatch_warning_flagging():
    """Verify warning is recorded when transaction date vs prior NAV date gap > tolerance."""
    meta = FundMetadata(100001, "Test Fund", "Test MF", "Category", "Type", "2023-01-01")
    # NAV history available only on 2022-01-01 and 2022-01-20 (gap of 9 days for a tx on 2022-01-10)
    nav_points = [(date(2022, 1, 1), 10.0), (date(2022, 1, 20), 12.0)]
    nav_history = FundNAVHistory(meta, nav_points)

    txs = [ParsedSIPTransaction(date=date(2022, 1, 10), scheme_code="100001", scheme_name=None, amount=1000.0)]

    units, val, eff_date, warnings = compute_units_and_current_value(
        transactions=txs,
        nav_history=nav_history,
        valuation_date=date(2022, 1, 20),
        max_mismatch_tolerance_days=5,
    )

    assert len(warnings) == 1
    assert "exceeds tolerance threshold of 5 days" in warnings[0]
    assert units == 100.0  # 1000 / 10.0 (prior NAV on 2022-01-01)


def test_transaction_earlier_than_nav_history_error():
    """Verify ValueError when transaction date precedes earliest fund NAV."""
    meta = FundMetadata(100001, "Test Fund", "Test MF", "Category", "Type", "2023-01-01")
    nav_history = FundNAVHistory(meta, [(date(2022, 1, 10), 10.0), (date(2022, 1, 20), 12.0)])

    # Tx dated 2022-01-01 (earlier than 2022-01-10)
    txs = [ParsedSIPTransaction(date=date(2022, 1, 1), scheme_code="100001", scheme_name=None, amount=1000.0)]

    with pytest.raises(ValueError, match="earlier than earliest available NAV date"):
        compute_units_and_current_value(txs, nav_history)


def test_valuation_date_later_than_nav_history_error():
    """Verify ValueError when requested valuation date exceeds latest fund NAV."""
    meta = FundMetadata(100001, "Test Fund", "Test MF", "Category", "Type", "2023-01-01")
    nav_history = FundNAVHistory(meta, [(date(2022, 1, 1), 10.0), (date(2022, 1, 20), 12.0)])

    txs = [ParsedSIPTransaction(date=date(2022, 1, 1), scheme_code="100001", scheme_name=None, amount=1000.0)]

    with pytest.raises(ValueError, match="later than latest available NAV date"):
        compute_units_and_current_value(txs, nav_history, valuation_date=date(2022, 2, 1))


def test_evaluate_all_funds_exception_isolation():
    """Verify evaluate_all_funds isolates exceptions per fund in batch execution."""
    meta1 = FundMetadata(100001, "Fund 1", "MF", "Cat", "Type", "2023-01-01")
    meta2 = FundMetadata(100002, "Fund 2", "MF", "Cat", "Type", "2023-01-01")

    nav_dates = [date(2022, 1, 1) + timedelta(days=i) for i in range(366)]
    nav1 = FundNAVHistory(meta1, [(dt, 10.0 + i*0.01) for i, dt in enumerate(nav_dates)])
    # Fund 2 has only 5 days of history -> will fail min_years_required date span validation
    nav2 = FundNAVHistory(meta2, [(date(2022, 1, 1) + timedelta(days=i), 10.0) for i in range(5)])

    benchmark_series = BenchmarkSeries("NIFTY50", "^NSEI", [(dt, 100.0 + i*0.01) for i, dt in enumerate(nav_dates)], "2023-01-01")

    txs = [
        ParsedSIPTransaction(date=date(2022, 1, 1), scheme_code="100001", scheme_name="Fund 1", amount=1000.0),
        ParsedSIPTransaction(date=date(2022, 1, 1), scheme_code="100002", scheme_name="Fund 2", amount=1000.0),
    ]

    histories = {"100001": nav1, "100002": nav2}

    results = evaluate_all_funds(txs, histories, benchmark_series, min_years_required=1.0)

    assert len(results) == 2
    assert isinstance(results["100001"], FundPerformanceResult)
    assert isinstance(results["100002"], Exception)
    assert "insufficient for the requested 1.0-year return analysis" in str(results["100002"])
