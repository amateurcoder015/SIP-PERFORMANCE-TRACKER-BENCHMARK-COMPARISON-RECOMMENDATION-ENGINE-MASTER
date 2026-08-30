"""
Unit tests for src/cagr.py module.

Includes hand-calculated point-to-point and rolling CAGR tests.
"""

from datetime import date, timedelta
import pytest

from src.cagr import calculate_cagr, rolling_cagr


def test_calculate_cagr_hand_verified():
    """
    Hand-calculated point-to-point CAGR tests.

    ARITHMETIC DERIVATIONS:
    ----------------------
    Case 1: Begin = 100.0, End = 144.0, Years = 2.0
      CAGR = (144 / 100)^(1/2) - 1 = sqrt(1.44) - 1 = 1.20 - 1 = 0.20 (20.00%)

    Case 2: Begin = 100.0, End = 200.0, Years = 5.0
      CAGR = (200 / 100)^(1/5) - 1 = 2^0.2 - 1 = 1.148698355 - 1 = 0.148698355 (14.8698355%)
    """
    res1 = calculate_cagr(100.0, 144.0, 2.0)
    assert pytest.approx(res1, abs=1e-6) == 0.20

    res2 = calculate_cagr(100.0, 200.0, 5.0)
    assert pytest.approx(res2, abs=1e-6) == 0.148698355


def test_calculate_cagr_edge_cases():
    """Verify input validations for calculate_cagr."""
    # Zero/negative begin value
    with pytest.raises(ValueError, match="begin_value must be strictly positive"):
        calculate_cagr(0.0, 150.0, 3.0)

    with pytest.raises(ValueError, match="begin_value must be strictly positive"):
        calculate_cagr(-10.0, 150.0, 3.0)

    # Negative end value
    with pytest.raises(ValueError, match="end_value cannot be negative"):
        calculate_cagr(100.0, -50.0, 3.0)

    # Zero/negative years
    with pytest.raises(ValueError, match="years must be strictly positive"):
        calculate_cagr(100.0, 150.0, 0.0)

    with pytest.raises(ValueError, match="years must be strictly positive"):
        calculate_cagr(100.0, 150.0, -1.0)

    # Zero end value (100% loss)
    assert calculate_cagr(100.0, 0.0, 3.0) == -1.0


def test_rolling_cagr_synthetic_series():
    """
    Test rolling_cagr against synthetic NAV series with hand-calculated expected values.

    SYNTHETIC DATA SETUP:
    --------------------
    - NAV series covering 4 years (2020-01-01 to 2024-01-01):
        2020-01-01: 100.0
        2021-01-01: 110.0
        2022-01-01: 121.0
        2023-01-01: 133.1 (3 years from 2020-01-01)
        2024-01-01: 146.41 (3 years from 2021-01-01, 4 years from 2020-01-01)
    
    ARITHMETIC EXPECTATIONS (3-Year Rolling CAGR):
    - At 2023-01-01:
        Start date: 2020-01-01 (NAV = 100.0), End date: 2023-01-01 (NAV = 133.1)
        Years = 1096 / 365.25 = 3.00068446
        CAGR = (133.1 / 100.0)^(1 / 3.00068446) - 1 = 1.331^(0.3332573) - 1 = 0.10 (10.0%)

    - At 2024-01-01:
        Start date: 2021-01-01 (NAV = 110.0), End date: 2024-01-01 (NAV = 146.41)
        Years = 1095 / 365.25 = 2.9979466
        CAGR = (146.41 / 110.0)^(1 / 2.9979466) - 1 = 1.331^(0.3335616) - 1 = 0.10 (10.0%)
    """
    nav_series = [
        (date(2020, 1, 1), 100.0),
        (date(2021, 1, 1), 110.0),
        (date(2022, 1, 1), 121.0),
        (date(2023, 1, 1), 133.1),
        (date(2024, 1, 1), 146.41),
    ]

    rolling_3y = rolling_cagr(nav_series, window_years=3.0)

    # First available rolling 3y point should be 2023-01-01
    assert len(rolling_3y) == 2
    assert rolling_3y[0][0] == date(2023, 1, 1)
    assert pytest.approx(rolling_3y[0][1], abs=1e-3) == 0.10

    assert rolling_3y[1][0] == date(2024, 1, 1)
    assert pytest.approx(rolling_3y[1][1], abs=1e-3) == 0.10


def test_rolling_cagr_invalid_window():
    """Check ValueError when window_years <= 0."""
    nav_series = [(date(2020, 1, 1), 100.0), (date(2021, 1, 1), 110.0)]
    with pytest.raises(ValueError, match="window_years must be strictly positive"):
        rolling_cagr(nav_series, window_years=0.0)
