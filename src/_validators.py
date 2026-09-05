"""
Shared input validation helpers for financial math calculations.

Provides rigorous validation rules for cashflows, NAV series, and rate inputs
to ensure clear error messages and prevent invalid numerical calculations.
"""

from datetime import date
from typing import Sequence, Tuple, Union


Cashflow = Tuple[date, float]
NAVPoint = Tuple[date, float]


def validate_cashflows(cashflows: Sequence[Cashflow]) -> list[Tuple[date, float]]:
    """
    Validate and normalize a list of cashflows.

    Parameters
    ----------
    cashflows : Sequence[Tuple[date, float]]
        List of (date, amount) tuples.

    Returns
    -------
    list[Tuple[date, float]]
        Validated list of (date, float_amount) tuples.

    Raises
    ------
    ValueError
        If input is not a sequence, contains fewer than 2 cashflows, contains
        invalid types, or does not contain both positive and negative cashflows.
    """
    if not isinstance(cashflows, (list, tuple)):
        raise ValueError(f"Cashflows must be a list or tuple of (date, amount) pairs, got {type(cashflows).__name__}")

    if len(cashflows) < 2:
        raise ValueError(f"At least 2 cashflows are required to compute XIRR, got {len(cashflows)}")

    normalized: list[Tuple[date, float]] = []
    has_positive = False
    has_negative = False

    for idx, item in enumerate(cashflows):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(
                f"Cashflow item at index {idx} must be a (date, amount) tuple, got {item!r}"
            )

        dt, amt = item

        if not isinstance(dt, date):
            raise ValueError(
                f"Cashflow date at index {idx} must be a datetime.date object, got {type(dt).__name__}"
            )

        try:
            float_amt = float(amt)
        except (TypeError, ValueError) as err:
            raise ValueError(
                f"Cashflow amount at index {idx} must be numeric, got {amt!r}"
            ) from err

        if float_amt > 0:
            has_positive = True
        elif float_amt < 0:
            has_negative = True

        normalized.append((dt, float_amt))

    if not (has_positive and has_negative):
        raise ValueError(
            "Cashflows must contain both negative (outflows/installments) and positive (inflow/valuation) amounts"
        )

    return normalized


def validate_nav_series(nav_series: Sequence[NAVPoint]) -> list[Tuple[date, float]]:
    """
    Validate and normalize a NAV or index price time series.

    Parameters
    ----------
    nav_series : Sequence[Tuple[date, float]]
        Time series of (date, nav_price) tuples.

    Returns
    -------
    list[Tuple[date, float]]
        Sorted, validated list of (date, float_nav) tuples.

    Raises
    ------
    ValueError
        If nav_series is empty, improperly formatted, or contains non-positive NAV values.
    """
    if not isinstance(nav_series, (list, tuple)):
        raise ValueError(f"NAV series must be a list or tuple, got {type(nav_series).__name__}")

    if len(nav_series) == 0:
        raise ValueError("NAV series cannot be empty")

    normalized: list[Tuple[date, float]] = []

    for idx, item in enumerate(nav_series):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(
                f"NAV point at index {idx} must be a (date, nav) tuple, got {item!r}"
            )

        dt, nav = item

        if not isinstance(dt, date):
            raise ValueError(
                f"NAV date at index {idx} must be a datetime.date object, got {type(dt).__name__}"
            )

        try:
            float_nav = float(nav)
        except (TypeError, ValueError) as err:
            raise ValueError(
                f"NAV value at index {idx} must be numeric, got {nav!r}"
            ) from err

        if float_nav <= 0:
            raise ValueError(
                f"NAV value at index {idx} must be strictly positive (> 0), got {float_nav}"
            )

        normalized.append((dt, float_nav))

    # Return sorted by date
    normalized.sort(key=lambda x: x[0])
    return normalized


def validate_sufficient_history(
    nav_series: Sequence[NAVPoint],
    required_years: float,
    min_annual_trading_days: float = 180.0,
) -> None:
    """
    Validate that a NAV time series covers a sufficient financial date span
    and possesses adequate data density (checking against major outages/gaps).

    Parameters
    ----------
    nav_series : Sequence[Tuple[date, float]]
        Time series of (date, nav) tuples.
    required_years : float
        Minimum required time span in years (e.g. 1.0, 3.0, 5.0).
    min_annual_trading_days : float, default 180.0
        Minimum required average NAV points per calendar year to catch severe data outages.

    Raises
    ------
    ValueError
        If nav_series span is less than required_years or data density is insufficient.
    """
    validated = validate_nav_series(nav_series)

    if required_years <= 0:
        raise ValueError(f"required_years must be strictly positive (> 0), got {required_years}")

    t_min = validated[0][0]
    t_max = validated[-1][0]
    total_days = (t_max - t_min).days

    required_days = int(round(required_years * 365.25))
    actual_years = total_days / 365.25

    if total_days < required_days:
        raise ValueError(
            f"Fund has {actual_years:.1f} years of NAV history ({t_min} to {t_max}), "
            f"which is insufficient for the requested {required_years}-year return analysis."
        )

    avg_annual_density = len(validated) / max(actual_years, 0.1)
    if avg_annual_density < min_annual_trading_days:
        raise ValueError(
            f"Fund NAV history has significant data gaps ({avg_annual_density:.1f} NAV points/year < {min_annual_trading_days:.1f} required threshold)."
        )
