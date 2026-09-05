"""
Unit tests for src/data_fetch.py module using frozen fixtures (Zero live network calls).
"""

from datetime import date
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.data_fetch import (
    fetch_benchmark_series,
    fetch_fund_nav_history,
    fetch_scheme_list,
    FundMetadata,
    FundNAVHistory,
    BenchmarkSeries,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_mfapi_120503():
    with open(FIXTURE_DIR / "mfapi_scheme_120503.json", "r") as f:
        return json.load(f)


@pytest.fixture
def mock_mfapi_122639():
    with open(FIXTURE_DIR / "mfapi_scheme_122639.json", "r") as f:
        return json.load(f)


@pytest.fixture
def mock_mfapi_120505():
    with open(FIXTURE_DIR / "mfapi_scheme_120505.json", "r") as f:
        return json.load(f)


@pytest.fixture
def mock_scheme_list():
    with open(FIXTURE_DIR / "mfapi_scheme_list_sample.json", "r") as f:
        return json.load(f)


def test_fetch_fund_nav_history_fixtures(mock_mfapi_120503, mock_mfapi_122639, mock_mfapi_120505):
    """Test fetch_fund_nav_history parses all 3 fixtures and enforces ASCENDING date ordering."""
    for fixture_data, expected_code in [(mock_mfapi_120503, 120503), (mock_mfapi_122639, 122639), (mock_mfapi_120505, 120505)]:
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture_data
            mock_get.return_value = mock_resp

            result = fetch_fund_nav_history(expected_code)

            assert isinstance(result, FundNAVHistory)
            assert result.metadata.scheme_code == expected_code
            assert len(result.nav_series) > 0

            # CRITICAL: Verify ASCENDING date ordering (oldest -> newest)
            dates = [dt for dt, _ in result.nav_series]
            assert dates == sorted(dates)
            assert dates[0] < dates[-1]


def test_fetch_fund_nav_history_invalid_scheme():
    """Test ValueError raised on 404 / invalid scheme code."""
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="not found on mfapi.in API"):
            fetch_fund_nav_history(999999)


def test_fetch_fund_nav_history_insufficient_points():
    """Test ValueError raised when NAV series has < 30 points."""
    short_data = {
        "status": "SUCCESS",
        "meta": {"scheme_code": 123456, "scheme_name": "Test Fund"},
        "data": [{"date": f"{i:02d}-01-2023", "nav": "10.0"} for i in range(1, 15)],
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = short_data
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="insufficient historical NAV points"):
            fetch_fund_nav_history(123456)


def test_fetch_scheme_list(mock_scheme_list):
    """Test fetch_scheme_list parses raw scheme list sample."""
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_scheme_list
        mock_get.return_value = mock_resp

        results = fetch_scheme_list()

        assert len(results) == len(mock_scheme_list)
        assert isinstance(results[0], FundMetadata)
        assert results[0].scheme_code == 100027


def test_fetch_benchmark_series_fixture():
    """Test fetch_benchmark_series parses fixture CSV and enforces ASCENDING date ordering."""
    nifty_df = pd.read_csv(FIXTURE_DIR / "benchmark_nifty50_sample.csv", index_col=0, parse_dates=True)

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = nifty_df
        mock_ticker_cls.return_value = mock_ticker_instance

        result = fetch_benchmark_series("NIFTY50")

        assert isinstance(result, BenchmarkSeries)
        assert result.ticker == "^NSEI"

        dates = [dt for dt, _ in result.level_series]
        assert dates == sorted(dates)
        assert dates[0] < dates[-1]


def test_fetch_benchmark_series_unsupported():
    """Test ValueError raised when requesting an unsupported benchmark name."""
    with pytest.raises(ValueError, match="Unsupported benchmark name 'NIFTYNEXT50'"):
        fetch_benchmark_series("NIFTYNEXT50")


def test_fetch_benchmark_series_insufficient_range():
    """Test ValueError raised when requested start date precedes available history."""
    nifty_df = pd.read_csv(FIXTURE_DIR / "benchmark_nifty50_sample.csv", index_col=0, parse_dates=True)

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = nifty_df
        mock_ticker_cls.return_value = mock_ticker_instance

        too_early_date = date(2000, 1, 1)
        with pytest.raises(ValueError, match="is earlier than earliest available benchmark history date"):
            fetch_benchmark_series("NIFTY50", start_date=too_early_date, end_date=date(2026, 1, 1))
