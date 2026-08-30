"""
CAGR (Compound Annual Growth Rate) and Rolling CAGR calculation module.

Provides point-to-point CAGR calculation and trailing rolling CAGR metrics over NAV time series.
"""

from datetime import date, timedelta
from typing import Sequence, Tuple
import bisect

from src._validators import validate_nav_series


def calculate_cagr(begin_value: float, end_value: float, years: float) -> float:
    """
    Calculate point-to-point Compound Annual Growth Rate (CAGR).

    Formula:
        (end_value / begin_value) ** (1 / years) - 1

    Parameters
    ----------
    begin_value : float
        Initial value (must be > 0).
    end_value : float
        Final value (must be >= 0).
    years : float
        Time period in years (must be > 0).

    Returns
    -------
    float
        CAGR as a decimal (e.g. 0.12 for 12%).

    Raises
    ------
    ValueError
        If begin_value <= 0, years <= 0, or end_value < 0.
    """
    try:
        b_val = float(begin_value)
        e_val = float(end_value)
        y_val = float(years)
    except (TypeError, ValueError) as err:
        raise ValueError(f"CAGR inputs must be numeric, got begin={begin_value!r}, end={end_value!r}, years={years!r}") from err

    if b_val <= 0:
        raise ValueError(f"begin_value must be strictly positive (> 0), got {b_val}")

    if e_val < 0:
        raise ValueError(f"end_value cannot be negative, got {e_val}")

    if y_val <= 0:
        raise ValueError(f"years must be strictly positive (> 0), got {y_val}")

    if e_val == 0:
        return -1.0

    return (e_val / b_val) ** (1.0 / y_val) - 1.0


def rolling_cagr(
    nav_series: Sequence[Tuple[date, float]],
    window_years: float,
    max_tolerance_days: int = 14,
) -> list[Tuple[date, float]]:
    """
    Compute trailing rolling CAGR across a NAV daily/weekly time series.

    At each NAV date t where data is available window_years prior, computes the
    CAGR using the nearest available prior NAV date within max_tolerance_days.

    Parameters
    ----------
    nav_series : Sequence[Tuple[date, float]]
        Time series of (date, nav_price) tuples.
    window_years : float
        Rolling window size in years (e.g. 3.0, 5.0).
    max_tolerance_days : int, default 14
        Maximum allowed difference in days between the ideal window start date
        and the nearest actual trading NAV date.

    Returns
    -------
    list[Tuple[date, float]]
        List of (current_date, rolling_cagr_decimal) tuples.

    Raises
    ------
    ValueError
        If nav_series is invalid or window_years <= 0.
    """
    if window_years <= 0:
        raise ValueError(f"window_years must be strictly positive (> 0), got {window_years}")

    validated_nav = validate_nav_series(nav_series)

    dates = [dt for dt, _ in validated_nav]
    navs = [nav for _, nav in validated_nav]

    target_delta_days = int(round(window_years * 365.25))

    results: list[Tuple[date, float]] = []

    for idx, curr_date in enumerate(dates):
        ideal_start_date = curr_date - timedelta(days=target_delta_days)

        # If ideal start date is earlier than the first available NAV minus tolerance, we can't compute
        if ideal_start_date < (dates[0] - timedelta(days=max_tolerance_days)):
            continue

        # Find closest date in dates array to ideal_start_date
        start_idx = _find_nearest_date_index(dates, ideal_start_date, max_tolerance_days)
        if start_idx is None:
            continue

        start_date, start_nav = dates[start_idx], navs[start_idx]
        curr_nav = navs[idx]

        # Calculate exact fractional year difference
        actual_days = (curr_date - start_date).days
        if actual_days <= 0:
            continue

        actual_years = actual_days / 365.25
        cagr = calculate_cagr(start_nav, curr_nav, actual_years)
        results.append((curr_date, cagr))

    return results


def _find_nearest_date_index(
    dates: list[date], target: date, max_tolerance_days: int
) -> int | None:
    """Find index of closest date to target within max_tolerance_days."""
    pos = bisect.bisect_left(dates, target)

    candidates = []
    if pos < len(dates):
        candidates.append((abs((dates[pos] - target).days), pos))
    if pos > 0:
        candidates.append((abs((dates[pos - 1] - target).days), pos - 1))

    if not candidates:
        return None

    best_diff, best_idx = min(candidates, key=lambda x: x[0])
    if best_diff <= max_tolerance_days:
        return best_idx

    return None
