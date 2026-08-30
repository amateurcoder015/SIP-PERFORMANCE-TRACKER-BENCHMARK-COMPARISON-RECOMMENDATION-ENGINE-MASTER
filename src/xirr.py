"""
XIRR (Extended Internal Rate of Return) calculation engine.

Computes the annualized money-weighted return (XIRR) for irregular cashflows.

SIGN CONVENTION (CRITICAL):
--------------------------
- Outflows (money paid by investor, e.g. SIP installments) MUST be NEGATIVE (< 0).
- Inflows (valuation amount or redemptions received by investor) MUST be POSITIVE (> 0).
- The final cashflow is typically the current valuation of holdings (units held * current NAV)
  dated as of the valuation date, with a positive value.
"""

from collections import defaultdict
from datetime import date
from typing import Sequence, Tuple
import numpy as np
from scipy.optimize import newton, brentq

from src._validators import validate_cashflows


def calculate_xirr(
    cashflows: Sequence[Tuple[date, float]],
    guess: float = 0.10,
    max_iter: int = 100,
    tol: float = 1e-7,
) -> float:
    """
    Calculate the Extended Internal Rate of Return (XIRR) for a series of cashflows.

    Solves for the rate r such that:
        sum( amount_i / (1 + r)**((date_i - date_0).days / 365.0) ) = 0

    Parameters
    ----------
    cashflows : Sequence[Tuple[date, float]]
        List of (date, amount) tuples.
        - SIP installments must be NEGATIVE (outflows).
        - Final current value / redemptions must be POSITIVE (inflows).
    guess : float, default 0.10
        Initial rate guess for iterative solver (0.10 = 10%).
    max_iter : int, default 100
        Maximum iterations allowed for numerical convergence.
    tol : float, default 1e-7
        Absolute tolerance for convergence.

    Returns
    -------
    float
        Annualized XIRR as a decimal (e.g. 0.145 for 14.5%).

    Raises
    ------
    ValueError
        If cashflows are invalid, fewer than 2 cashflows, all cashflows have the
        same sign, duplicate dates reduce valid cashflows below 2, or the numerical
        solver fails to converge.
    """
    # Validate raw structure and sign change presence
    validated = validate_cashflows(cashflows)

    # Net duplicate dates by summing cashflow amounts on identical dates
    netted_map: defaultdict[date, float] = defaultdict(float)
    for dt, amt in validated:
        netted_map[dt] += amt

    # Sort netted cashflows chronologically
    sorted_cashflows = sorted(netted_map.items(), key=lambda x: x[0])

    if len(sorted_cashflows) < 2:
        raise ValueError(
            "Cashflows must contain at least 2 distinct dates after netting duplicate dates"
        )

    # Verify netted cashflows still contain both negative and positive values
    has_pos = any(amt > 0 for _, amt in sorted_cashflows)
    has_neg = any(amt < 0 for _, amt in sorted_cashflows)
    if not (has_pos and has_neg):
        raise ValueError(
            "Cashflows after netting duplicate dates must contain both positive and negative amounts"
        )

    d0 = sorted_cashflows[0][0]
    days_array = np.array([(dt - d0).days for dt, _ in sorted_cashflows], dtype=np.float64)
    amounts_array = np.array([amt for _, amt in sorted_cashflows], dtype=np.float64)
    years_array = days_array / 365.0

    def npv(r: float) -> float:
        if r <= -1.0:
            return float("inf")
        return float(np.sum(amounts_array * ((1.0 + r) ** (-years_array))))

    def npv_prime(r: float) -> float:
        if r <= -1.0:
            return float("-inf")
        return float(np.sum(-years_array * amounts_array * ((1.0 + r) ** (-years_array - 1.0))))

    # Try Newton-Raphson first
    try:
        r_solution = newton(
            func=npv,
            x0=guess,
            fprime=npv_prime,
            tol=tol,
            maxiter=max_iter,
        )
        if not np.isnan(r_solution) and not np.isinf(r_solution) and r_solution > -1.0:
            # Double check NPV residual is acceptably close to zero
            if abs(npv(r_solution)) < 1e-3:
                return float(r_solution)
    except (RuntimeError, ValueError, OverflowError, ZeroDivisionError):
        pass

    # Fallback to secant method without derivative if Newton derivative step failed
    try:
        r_solution = newton(
            func=npv,
            x0=guess,
            tol=tol,
            maxiter=max_iter,
        )
        if not np.isnan(r_solution) and not np.isinf(r_solution) and r_solution > -1.0:
            if abs(npv(r_solution)) < 1e-3:
                return float(r_solution)
    except (RuntimeError, ValueError, OverflowError, ZeroDivisionError):
        pass

    # Fallback to Brent's method by scanning for a sign change interval
    bracket = _find_bracket(npv, min_r=-0.999, max_r=50.0, steps=200)
    if bracket is not None:
        low, high = bracket
        try:
            r_solution = brentq(npv, low, high, xtol=tol, maxiter=max_iter)
            return float(r_solution)
        except (RuntimeError, ValueError):
            pass

    raise ValueError(
        "XIRR calculation failed to converge. Please verify cashflow amounts and dates."
    )


def _find_bracket(
    func, min_r: float = -0.999, max_r: float = 50.0, steps: int = 200
) -> Tuple[float, float] | None:
    """Find a sign change bracket [a, b] for function f."""
    r_grid = np.linspace(min_r, max_r, steps)
    prev_r = r_grid[0]
    prev_val = func(prev_r)

    for r in r_grid[1:]:
        val = func(r)
        if np.isnan(val) or np.isinf(val):
            continue
        if prev_val * val <= 0:
            return (prev_r, r)
        prev_r = r
        prev_val = val

    return None
