"""
Per-Fund Performance Engine (YOU vs. BENCHMARK).

Orchestrates actual fund XIRR calculation, benchmark cashflow replication,
and comparative return analysis (alpha).
"""

import bisect
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple, Union

from src._validators import validate_sufficient_history
from src.cashflow_replication import replicate_cashflows_in_benchmark
from src.data_fetch import BenchmarkSeries, FundNAVHistory, ParsedSIPTransaction
from src.xirr import calculate_xirr


@dataclass
class FundPerformanceResult:
    """Structured performance comparison result for a single fund vs benchmark."""

    scheme_code: str
    scheme_name: str
    total_invested: float
    current_value: float
    units_held: float
    effective_valuation_date: date
    actual_xirr: float
    benchmark_name: str
    benchmark_xirr: float
    alpha: float
    absolute_gain: float
    num_transactions: int
    investment_span_years: float
    nav_date_mismatch_warnings: List[str]


def compute_units_and_current_value(
    transactions: Sequence[ParsedSIPTransaction],
    nav_history: FundNAVHistory,
    valuation_date: Optional[date] = None,
    max_mismatch_tolerance_days: int = 5,
) -> Tuple[float, float, date, List[str]]:
    """
    Calculate accumulated fund units, current valuation, and date mismatch warnings.

    Parameters
    ----------
    transactions : Sequence[ParsedSIPTransaction]
        Parsed SIP transactions for the target fund.
    nav_history : FundNAVHistory
        Historical daily NAV time series for the target fund.
    valuation_date : Optional[date]
        Target valuation date (defaults to latest available NAV date).
    max_mismatch_tolerance_days : int, default 5
        Tolerance in calendar days for flagging transaction date vs nearest prior NAV date mismatch.

    Returns
    -------
    Tuple[float, float, date, List[str]]
        (total_units_held, current_value, effective_valuation_date, warnings)

    Raises
    ------
    ValueError
        If transactions list is empty, transaction precedes fund NAV history,
        or requested valuation_date succeeds latest available NAV date.
    """
    if not transactions:
        raise ValueError("No transactions provided to compute units and current value.")

    sorted_txs = sorted(transactions, key=lambda x: x.date)

    nav_dates = [dt for dt, _ in nav_history.nav_series]
    nav_values = [nav for _, nav in nav_history.nav_series]

    earliest_nav_date = nav_dates[0]
    latest_nav_date = nav_dates[-1]

    warnings: List[str] = []
    total_units_held = 0.0

    for tx in sorted_txs:
        if tx.date < earliest_nav_date:
            raise ValueError(
                f"Transaction date {tx.date} is earlier than earliest available NAV date {earliest_nav_date} "
                f"for scheme code {nav_history.metadata.scheme_code} ({nav_history.metadata.scheme_name})."
            )

        # Find nearest PRIOR available NAV date
        idx = bisect.bisect_right(nav_dates, tx.date) - 1
        if idx < 0:
            raise ValueError(
                f"No available NAV found on or prior to transaction date {tx.date} for scheme {nav_history.metadata.scheme_code}."
            )

        nav_date_used = nav_dates[idx]
        nav_val_used = nav_values[idx]

        gap = (tx.date - nav_date_used).days
        if gap > max_mismatch_tolerance_days:
            warnings.append(
                f"Transaction on {tx.date} matched prior NAV date {nav_date_used} "
                f"(gap of {gap} days exceeds tolerance threshold of {max_mismatch_tolerance_days} days)."
            )

        units = tx.amount / nav_val_used
        total_units_held += units

    # Handle effective valuation date
    if valuation_date is None:
        eff_val_date = latest_nav_date
        val_idx = len(nav_dates) - 1
    else:
        if valuation_date > latest_nav_date:
            raise ValueError(
                f"Requested valuation date {valuation_date} is later than latest available NAV date {latest_nav_date} "
                f"for scheme {nav_history.metadata.scheme_code}."
            )

        val_idx = bisect.bisect_right(nav_dates, valuation_date) - 1
        if val_idx < 0:
            raise ValueError(
                f"No available NAV found on or prior to requested valuation date {valuation_date} for scheme {nav_history.metadata.scheme_code}."
            )
        eff_val_date = nav_dates[val_idx]

    val_nav = nav_values[val_idx]
    current_value = total_units_held * val_nav

    return total_units_held, current_value, eff_val_date, warnings


def evaluate_fund_performance(
    transactions: Sequence[ParsedSIPTransaction],
    nav_history: FundNAVHistory,
    benchmark_series: BenchmarkSeries,
    valuation_date: Optional[date] = None,
    min_years_required: float = 1.0,
) -> FundPerformanceResult:
    """
    Evaluate actual fund XIRR, benchmark-equivalent XIRR, and alpha for a single fund.

    Parameters
    ----------
    transactions : Sequence[ParsedSIPTransaction]
        Parsed transaction records.
    nav_history : FundNAVHistory
        NAV history for the target fund.
    benchmark_series : BenchmarkSeries
        Benchmark index level history.
    valuation_date : Optional[date]
        Target valuation date.
    min_years_required : float, default 1.0
        Minimum required investment span in years.

    Returns
    -------
    FundPerformanceResult
        Structured comparison result.

    Raises
    ------
    ValueError
        If no matching transactions are found, or Step 1/2 validation errors occur.
    """
    scheme_code_str = str(nav_history.metadata.scheme_code).strip()
    scheme_name_str = str(nav_history.metadata.scheme_name).strip()

    filtered_txs = [
        t
        for t in transactions
        if str(t.scheme_code).strip() == scheme_code_str
        or (t.scheme_name and str(t.scheme_name).strip() == scheme_name_str)
    ]

    if not filtered_txs:
        raise ValueError(f"No transactions found matching scheme code '{scheme_code_str}' / '{scheme_name_str}'.")

    sorted_txs = sorted(filtered_txs, key=lambda x: x.date)
    t_first = sorted_txs[0].date

    # Compute units, current valuation, and effective valuation date
    units_held, current_value, eff_val_date, warnings = compute_units_and_current_value(
        transactions=sorted_txs,
        nav_history=nav_history,
        valuation_date=valuation_date,
    )

    # Validate investor's actual transaction window span
    investor_nav_window = [p for p in nav_history.nav_series if t_first <= p[0] <= eff_val_date]
    if not investor_nav_window:
        investor_nav_window = nav_history.nav_series

    validate_sufficient_history(investor_nav_window, required_years=min_years_required)

    # 1. Build ACTUAL investor cashflows (negate contribution outflows)
    actual_cashflows = [(t.date, -t.amount) for t in sorted_txs] + [(eff_val_date, current_value)]
    actual_xirr = calculate_xirr(actual_cashflows)

    # 2. Build FUND cashflows for benchmark replication
    fund_cashflows = [(t.date, -t.amount) for t in sorted_txs] + [(eff_val_date, current_value)]
    replicated_bm_cashflows = replicate_cashflows_in_benchmark(
        fund_cashflows=fund_cashflows,
        benchmark_nav_series=benchmark_series.level_series,
    )

    # Compute benchmark-equivalent XIRR
    benchmark_xirr = calculate_xirr(replicated_bm_cashflows)
    alpha = actual_xirr - benchmark_xirr

    total_invested = sum(t.amount for t in sorted_txs)
    absolute_gain = current_value - total_invested
    investment_span_years = (eff_val_date - t_first).days / 365.25

    return FundPerformanceResult(
        scheme_code=scheme_code_str,
        scheme_name=scheme_name_str,
        total_invested=total_invested,
        current_value=current_value,
        units_held=units_held,
        effective_valuation_date=eff_val_date,
        actual_xirr=actual_xirr,
        benchmark_name=benchmark_series.benchmark_name,
        benchmark_xirr=benchmark_xirr,
        alpha=alpha,
        absolute_gain=absolute_gain,
        num_transactions=len(sorted_txs),
        investment_span_years=investment_span_years,
        nav_date_mismatch_warnings=warnings,
    )


def evaluate_all_funds(
    transactions: Sequence[ParsedSIPTransaction],
    nav_histories: Dict[str, FundNAVHistory],
    benchmark_series: BenchmarkSeries,
    valuation_date: Optional[date] = None,
    min_years_required: float = 1.0,
) -> Dict[str, Union[FundPerformanceResult, Exception]]:
    """
    Evaluate performance for multiple funds from a batch transaction list.

    Per-Fund Exception Isolation:
    -----------------------------
    If evaluating a specific scheme raises an exception (e.g. insufficient history for one fund),
    the exception instance is CAPTURED as the dict value for that scheme_code rather than aborting
    the evaluation of other funds.

    Parameters
    ----------
    transactions : Sequence[ParsedSIPTransaction]
        Full multi-fund transaction list.
    nav_histories : Dict[str, FundNAVHistory]
        Map of scheme_code -> FundNAVHistory.
    benchmark_series : BenchmarkSeries
        Benchmark index history.
    valuation_date : Optional[date]
        Target valuation date.
    min_years_required : float, default 1.0
        Minimum required investment span in years.

    Returns
    -------
    Dict[str, Union[FundPerformanceResult, Exception]]
        Map of scheme_code -> FundPerformanceResult or Exception.
    """
    results: Dict[str, Union[FundPerformanceResult, Exception]] = {}

    for code_key, nav_history in nav_histories.items():
        try:
            res = evaluate_fund_performance(
                transactions=transactions,
                nav_history=nav_history,
                benchmark_series=benchmark_series,
                valuation_date=valuation_date,
                min_years_required=min_years_required,
            )
            results[code_key] = res
        except Exception as exc:
            results[code_key] = exc

    return results
