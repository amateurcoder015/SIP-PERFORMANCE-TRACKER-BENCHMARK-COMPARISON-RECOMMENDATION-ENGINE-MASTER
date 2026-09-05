"""
Integration test making REAL live network calls to mfapi.in and yfinance endpoints.
Marked with @pytest.mark.integration to allow exclusion during fast offline unit runs.
"""

from datetime import date, timedelta
import pytest

from src.data_fetch import fetch_benchmark_series, fetch_fund_nav_history, FundNAVHistory, BenchmarkSeries


@pytest.mark.integration
def test_live_network_data_fetch():
    """
    Real live network integration test.

    Calls mfapi.in for Parag Parikh Flexi Cap (122639) and yfinance for Nifty 50 (^NSEI).
    Asserts real data is retrieved, normalized ascending, and non-empty.
    """
    # 1. Real mfapi.in live network fetch
    fund_history = fetch_fund_nav_history(122639)

    assert isinstance(fund_history, FundNAVHistory)
    assert fund_history.metadata.scheme_code == 122639
    assert "Parag Parikh" in fund_history.metadata.scheme_name
    assert len(fund_history.nav_series) > 1000  # Multi-year daily series

    # Verify ASCENDING date order
    nav_dates = [dt for dt, _ in fund_history.nav_series]
    assert nav_dates == sorted(nav_dates)
    assert nav_dates[0] < nav_dates[-1]

    # 2. Real yfinance live network fetch
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=365)
    bm_series = fetch_benchmark_series("NIFTY50", start_date=start_dt, end_date=end_dt)

    assert isinstance(bm_series, BenchmarkSeries)
    assert bm_series.ticker == "^NSEI"
    assert len(bm_series.level_series) > 200

    # Verify ASCENDING date order
    bm_dates = [dt for dt, _ in bm_series.level_series]
    assert bm_dates == sorted(bm_dates)
    assert bm_dates[0] < bm_dates[-1]
