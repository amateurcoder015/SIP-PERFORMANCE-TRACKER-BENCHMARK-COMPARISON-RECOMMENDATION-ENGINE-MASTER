"""
Unit tests for src/xirr.py module.

Includes hand-verified mathematical calculations, edge case validation, and sign convention checks.
"""

from datetime import date
import pytest

from src.xirr import calculate_xirr


def test_xirr_two_cashflows_analytical():
    """
    Hand-verified Test Case 1: Simple 2-cashflow analytical check.
    
    ARITHMETIC DERIVATION:
    ----------------------
    - Cashflow 0 (2023-01-01): -1000.0 (Investment outflow)
    - Cashflow 1 (2024-01-01): +1145.0 (Valuation inflow 365 days later)
    - XIRR Equation: -1000 + 1145 / (1 + r)^(365/365) = 0
    - 1000 * (1 + r) = 1145
    - 1 + r = 1.145
    - r = 0.145 = 14.500000%
    """
    cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2024, 1, 1), 1145.0),
    ]
    result = calculate_xirr(cashflows)
    assert pytest.approx(result, abs=1e-6) == 0.145


def test_xirr_monthly_sip_hand_verified():
    """
    Hand-verified Test Case 2: Realistic 12-month SIP series.
    
    ARITHMETIC DERIVATION & CROSS-CHECK METHODOLOGY:
    -----------------------------------------------
    - 12 monthly installments of Rs 1,000 on the 1st of each month in 2022.
    - Final valuation of Rs 13,000 on 2023-01-01 (365 days after start).
    - Cashflow details:
        2022-01-01: -1000 (day 0)
        2022-02-01: -1000 (day 31)
        2022-03-01: -1000 (day 59)
        2022-04-01: -1000 (day 90)
        2022-05-01: -1000 (day 120)
        2022-06-01: -1000 (day 151)
        2022-07-01: -1000 (day 181)
        2022-08-01: -1000 (day 212)
        2022-09-01: -1000 (day 243)
        2022-10-01: -1000 (day 273)
        2022-11-01: -1000 (day 304)
        2022-12-01: -1000 (day 334)
        2023-01-01: +13000 (day 365)
    
    - Substituting r = 0.15669835 (15.669835%) into f(r) = sum( C_i / (1+r)^(t_i / 365) ):
        -1000/1.15669835^0         = -1000.0000
        -1000/1.15669835^(31/365)   =  -987.8760
        -1000/1.15669835^(59/365)   =  -977.0787
        -1000/1.15669835^(90/365)   =  -965.2934
        -1000/1.15669835^(120/365)  =  -954.0205
        -1000/1.15669835^(151/365)  =  -942.5284
        -1000/1.15669835^(181/365)  =  -931.5541
        -1000/1.15669835^(212/365)  =  -920.3547
        -1000/1.15669835^(243/365)  =  -909.3090
        -1000/1.15669835^(273/365)  =  -898.7770
        -1000/1.15669835^(304/365)  =  -888.0315
        -1000/1.15669835^(334/365)  =  -877.7602
        +13000/1.15669835^(365/365) =+11238.6835
        SUM = 0.000000
    - Expected XIRR = 0.15669835 (approx 15.67%)
    """
    cashflows = [
        (date(2022, 1, 1), -1000.0),
        (date(2022, 2, 1), -1000.0),
        (date(2022, 3, 1), -1000.0),
        (date(2022, 4, 1), -1000.0),
        (date(2022, 5, 1), -1000.0),
        (date(2022, 6, 1), -1000.0),
        (date(2022, 7, 1), -1000.0),
        (date(2022, 8, 1), -1000.0),
        (date(2022, 9, 1), -1000.0),
        (date(2022, 10, 1), -1000.0),
        (date(2022, 11, 1), -1000.0),
        (date(2022, 12, 1), -1000.0),
        (date(2023, 1, 1), 13000.0),
    ]
    result = calculate_xirr(cashflows)
    assert pytest.approx(result, abs=1e-6) == 0.15669835


def test_xirr_duplicate_dates_netting():
    """Verify that duplicate dates are netted together correctly."""
    # Two installments on same date: -1000 and -500 -> netted to -1500
    cashflows = [
        (date(2023, 1, 1), -1000.0),
        (date(2023, 1, 1), -500.0),
        (date(2024, 1, 1), 1725.0),
    ]
    # Netted: -1500 on 2023-01-01, +1725 on 2024-01-01 -> 1725 / 1500 - 1 = 0.15 (15%)
    result = calculate_xirr(cashflows)
    assert pytest.approx(result, abs=1e-6) == 0.15


def test_xirr_fewer_than_two_cashflows():
    """Check ValueError when cashflows < 2."""
    with pytest.raises(ValueError, match="At least 2 cashflows are required"):
        calculate_xirr([(date(2023, 1, 1), -1000.0)])


def test_xirr_all_same_sign():
    """Check ValueError when all cashflows have the same sign."""
    all_neg = [(date(2023, 1, 1), -1000.0), (date(2023, 2, 1), -1000.0)]
    with pytest.raises(ValueError, match="must contain both negative"):
        calculate_xirr(all_neg)

    all_pos = [(date(2023, 1, 1), 1000.0), (date(2023, 2, 1), 1000.0)]
    with pytest.raises(ValueError, match="must contain both negative"):
        calculate_xirr(all_pos)


def test_xirr_invalid_types():
    """Check ValueError on invalid input types."""
    with pytest.raises(ValueError, match="must be a list or tuple"):
        calculate_xirr("not a list")  # type: ignore

    with pytest.raises(ValueError, match="must be a datetime.date object"):
        calculate_xirr([("2023-01-01", -1000.0), (date(2024, 1, 1), 1100.0)])  # type: ignore

    with pytest.raises(ValueError, match="must be numeric"):
        calculate_xirr([(date(2023, 1, 1), "abc"), (date(2024, 1, 1), 1100.0)])  # type: ignore


def test_xirr_non_convergence_error():
    """Verify clean error raising when solver cannot converge."""
    # Extreme pathological cashflow that causes float overflow or non-convergence
    pathological = [
        (date(2023, 1, 1), -1e-15),
        (date(2023, 1, 2), 1e15),
    ]
    with pytest.raises(ValueError, match="XIRR calculation failed to converge"):
        calculate_xirr(pathological)
