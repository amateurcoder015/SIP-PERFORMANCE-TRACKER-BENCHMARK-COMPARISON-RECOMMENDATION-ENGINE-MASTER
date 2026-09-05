"""
Unit tests for FastAPI backend API endpoints in api/main.py.

Uses FastAPI TestClient and unittest.mock to test request/response serialization,
error handling, per-fund isolation, and mandatory disclaimer enforcement.
"""

from datetime import date
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from api.main import app
from src.data_fetch import BenchmarkSeries, FundMetadata, FundNAVHistory, ParsedSIPTransaction
from src.performance_engine import FundPerformanceResult
from src.recommendation_engine import (
    FundScore,
    MANDATORY_DISCLAIMER,
    RecommendationResult,
)


client = TestClient(app)


def test_health_check():
    """Verify GET /api/health returns 200 OK."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_upload_transactions_valid_csv():
    """Verify POST /api/upload-transactions successfully parses uploaded CSV buffer."""
    csv_content = (
        "date,scheme_code,scheme_name,amount\n"
        "2021-01-01,122639,Parag Parikh Flexi Cap Fund,10000\n"
        "2021-02-01,122639,Parag Parikh Flexi Cap Fund,10000\n"
    ).encode("utf-8")

    files = {"file": ("transactions.csv", csv_content, "text/csv")}
    res = client.post("/api/upload-transactions", files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["total_transactions"] == 2
    assert len(data["schemes"]) == 1
    assert data["schemes"][0]["scheme_code"] == "122639"
    assert data["schemes"][0]["transaction_count"] == 2
    assert data["schemes"][0]["total_amount"] == 20000.0


def test_upload_transactions_missing_columns_error():
    """Verify POST /api/upload-transactions returns 400 Bad Request on missing CSV columns."""
    invalid_csv = "date,amount\n2021-01-01,10000\n".encode("utf-8")
    files = {"file": ("bad.csv", invalid_csv, "text/csv")}

    res = client.post("/api/upload-transactions", files=files)
    assert res.status_code == 400
    assert "Unrecognized CSV format" in res.json()["detail"]


def test_evaluate_performance_success_and_per_fund_isolation():
    """
    Verify POST /api/performance serializes results correctly and handles per-fund exception isolation.
    """
    payload = {
        "transactions": [
            {"date": "2021-01-01", "scheme_code": "100", "scheme_name": "Fund 100", "amount": 10000.0},
            {"date": "2021-01-01", "scheme_code": "200", "scheme_name": "Fund 200", "amount": 5000.0},
        ],
        "benchmark_name": "NIFTY50",
        "valuation_date": "2022-01-01",
        "min_years_required": 1.0,
    }

    # Mock FundPerformanceResult for Fund 100
    perf_100 = FundPerformanceResult(
        scheme_code="100",
        scheme_name="Fund 100",
        total_invested=10000.0,
        current_value=12000.0,
        units_held=100.0,
        effective_valuation_date=date(2022, 1, 1),
        actual_xirr=0.185,
        benchmark_name="NIFTY50",
        benchmark_xirr=0.120,
        alpha=0.065,
        absolute_gain=2000.0,
        num_transactions=1,
        investment_span_years=1.0,
        nav_date_mismatch_warnings=[],
    )

    # Fund 200 fails with ValueError
    mock_eval_results = {
        "100": perf_100,
        "200": ValueError("Fund 200 has insufficient NAV history."),
    }

    mock_bm_series = BenchmarkSeries("NIFTY50", "^NSEI", [(date(2021, 1, 1), 14000.0)], "2022-01-01")
    mock_nav_history = FundNAVHistory(
        FundMetadata(100, "Fund 100", "House", "Cat", "Type", "2022-01-01"),
        [(date(2021, 1, 1), 100.0)],
    )

    mock_scheme_list = [
        FundMetadata(100, "Fund 100", "House", "Cat", "Type", "2022-01-01"),
        FundMetadata(200, "Fund 200", "House", "Cat", "Type", "2022-01-01"),
    ]

    with patch("api.main.fetch_scheme_list", return_value=mock_scheme_list):
        with patch("api.main.fetch_benchmark_series", return_value=mock_bm_series):
            with patch("api.main.get_cached_nav_history", return_value=mock_nav_history):
                with patch("api.main.evaluate_all_funds", return_value=mock_eval_results):
                    res = client.post("/api/performance", json=payload)

                assert res.status_code == 200
                data = res.json()

                # Fund 100 serialized successfully
                assert "100" in data
                assert data["100"]["actual_xirr"] == 0.185
                assert data["100"]["alpha"] == 0.065
                assert data["100"]["effective_valuation_date"] == "2022-01-01"

                # Fund 200 isolated error recorded
                assert "200" in data
                assert "error" in data["200"]
                assert "insufficient NAV history" in data["200"]["error"]


def test_evaluate_performance_invalid_date_error():
    """Verify POST /api/performance returns 400 when date string format is invalid."""
    payload = {
        "transactions": [{"date": "01-01-2021", "scheme_code": "100", "amount": 10000.0}],
        "benchmark_name": "NIFTY50",
    }
    res = client.post("/api/performance", json=payload)
    assert res.status_code == 400
    assert "Invalid date format" in res.json()["detail"]


def test_recommend_peers_success_and_disclaimer():
    """
    Verify POST /api/recommend returns serialized RecommendationResult with disclaimer intact.
    """
    payload = {
        "target_scheme_code": "122639",
        "max_candidates_to_confirm": 15,
        "top_n": 3,
        "min_years_required": 3.0,
    }

    target_score = FundScore(
        scheme_code="122639",
        scheme_name="Parag Parikh Flexi Cap",
        normalized_category="Flexi Cap",
        windows_used=[3.0, 5.0],
        mean_rolling_cagr_by_window={"3y": 0.18, "5y": 0.16},
        stdev_rolling_cagr_by_window={"3y": 0.08, "5y": 0.07},
        risk_adjusted_metric=1.5,
        composite_score=0.820,
    )

    rec_peer = FundScore(
        scheme_code="120843",
        scheme_name="Quant Flexi Cap",
        normalized_category="Flexi Cap",
        windows_used=[3.0, 5.0],
        mean_rolling_cagr_by_window={"3y": 0.21, "5y": 0.18},
        stdev_rolling_cagr_by_window={"3y": 0.10, "5y": 0.09},
        risk_adjusted_metric=1.6,
        composite_score=0.819,
    )

    mock_rec_result = RecommendationResult(
        target_score=target_score,
        normalized_category="Flexi Cap",
        recommendations=[rec_peer],
        reasoning={"120843": "Ranked #1 in Flexi Cap category"},
        skipped_funds=[],
        candidates_confirmed_count=10,
        disclaimer=MANDATORY_DISCLAIMER,
    )

    with patch("api.main.recommend_alternatives", return_value=mock_rec_result):
        res = client.post("/api/recommend", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["normalized_category"] == "Flexi Cap"
        assert data["target_score"]["composite_score"] == 0.820
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["scheme_code"] == "120843"
        assert data["reasoning"]["120843"] == "Ranked #1 in Flexi Cap category"

        # Mandatory disclaimer presence and exact text match
        assert "disclaimer" in data
        assert data["disclaimer"] == MANDATORY_DISCLAIMER
        assert "NOT FINANCIAL ADVICE" in data["disclaimer"]


def test_recommend_peers_invalid_code_error():
    """Verify POST /api/recommend returns 400 when scheme code raises ValueError."""
    payload = {"target_scheme_code": "999999"}
    with patch("api.main.recommend_alternatives", side_effect=ValueError("Scheme code '999999' not found.")):
        res = client.post("/api/recommend", json=payload)
        assert res.status_code == 400
        assert "not found" in res.json()["detail"]
