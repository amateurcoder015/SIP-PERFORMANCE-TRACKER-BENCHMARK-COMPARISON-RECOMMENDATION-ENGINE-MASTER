"""
Benchmark cashflow replication simulation engine.

Simulates "what if these exact same cashflows went into a benchmark index instead".
Converts actual mutual fund SIP cashflows into benchmark-equivalent cashflows
for an apples-to-apples XIRR comparison.
"""

from datetime import date
from typing import Sequence, Tuple
import bisect

from src._validators import validate_cashflows, validate_nav_series


def replicate_cashflows_in_benchmark(
    fund_cashflows: Sequence[Tuple[date, float]],
    benchmark_nav_series: Sequence[Tuple[date, float]],
) -> list[Tuple[date, float]]:
    """
    Replicate fund SIP cashflows in a benchmark index time series.

    For every SIP installment (negative amount), computes how many units of the
    benchmark index would have been purchased at the nearest prior trading date's
    benchmark level. Accumulates total units, and computes the benchmark-equivalent
    valuation on the final date.

    DATE-MATCHING CONVENTION:
    -------------------------
    If a fund cashflow date does not exist in the benchmark series (e.g. market
    holiday or weekend), the function selects the nearest available PRIOR trading date.
    If the benchmark series begins later than the first fund cashflow date, a ValueError is raised.

    INPUT CONSTRAINTS:
    ------------------
    - All intermediate cashflows (before the final element) MUST be negative (< 0, outflows).
    - Any intermediate positive cashflow (e.g. partial redemption) is rejected with ValueError.
    - The final cashflow element MUST be positive (> 0, valuation date).

    Parameters
    ----------
    fund_cashflows : Sequence[Tuple[date, float]]
        Chronological list of fund cashflows (date, amount).
    benchmark_nav_series : Sequence[Tuple[date, float]]
        Time series of (date, benchmark_index_level) tuples.

    Returns
    -------
    list[Tuple[date, float]]
        New list of cashflows with identical contribution amounts/dates, but with
        the final valuation amount replaced by the benchmark-equivalent value.

    Raises
    ------
    ValueError
        If inputs are invalid, benchmark series doesn't cover cashflow dates, or
        intermediate cashflows contain positive values.
    """
    validated_cf = validate_cashflows(fund_cashflows)
    validated_bm = validate_nav_series(benchmark_nav_series)

    # Sort fund cashflows by date
    sorted_cf = sorted(validated_cf, key=lambda x: x[0])

    bm_dates = [dt for dt, _ in validated_bm]
    bm_navs = [nav for _, nav in validated_bm]

    bm_start_date = bm_dates[0]
    first_cf_date = sorted_cf[0][0]

    if bm_start_date > first_cf_date:
        raise ValueError(
            f"Benchmark NAV series starts on {bm_start_date}, which is later than the "
            f"first fund cashflow date {first_cf_date}. Benchmark data coverage must start on or before the first SIP installment."
        )

    # Verify cashflow structure: all intermediate elements must be negative, final must be positive
    for idx, (dt, amt) in enumerate(sorted_cf[:-1]):
        if amt >= 0:
            raise ValueError(
                f"Intermediate cashflow at index {idx} on date {dt} is non-negative ({amt}). "
                "replicate_cashflows_in_benchmark only supports SIP installment contribution histories "
                "where all intermediate cashflows are negative outflows."
            )

    final_date, final_amt = sorted_cf[-1]
    if final_amt <= 0:
        raise ValueError(
            f"Final cashflow on valuation date {final_date} must be strictly positive (> 0), got {final_amt}"
        )

    total_benchmark_units = 0.0
    replicated_cashflows: list[Tuple[date, float]] = []

    # Process all installment cashflows (negative amounts)
    for dt, amt in sorted_cf[:-1]:
        bm_idx = _find_nearest_prior_bm_index(bm_dates, dt)
        if bm_idx is None:
            raise ValueError(
                f"No benchmark NAV available on or prior to fund cashflow date {dt}."
            )

        bm_nav_on_date = bm_navs[bm_idx]
        units_bought = abs(amt) / bm_nav_on_date
        total_benchmark_units += units_bought

        # Replicated installment has identical date and negative outflow amount
        replicated_cashflows.append((dt, amt))

    # Process final valuation cashflow
    final_bm_idx = _find_nearest_prior_bm_index(bm_dates, final_date)
    if final_bm_idx is None:
        raise ValueError(
            f"No benchmark NAV available on or prior to final valuation date {final_date}."
        )

    final_bm_nav = bm_navs[final_bm_idx]
    benchmark_final_valuation = total_benchmark_units * final_bm_nav

    replicated_cashflows.append((final_date, benchmark_final_valuation))

    return replicated_cashflows


def _find_nearest_prior_bm_index(bm_dates: list[date], target_date: date) -> int | None:
    """
    Find the index of the nearest available date in bm_dates that is <= target_date.

    Returns None if target_date is strictly earlier than bm_dates[0].
    """
    pos = bisect.bisect_right(bm_dates, target_date)
    if pos == 0:
        return None
    return pos - 1
