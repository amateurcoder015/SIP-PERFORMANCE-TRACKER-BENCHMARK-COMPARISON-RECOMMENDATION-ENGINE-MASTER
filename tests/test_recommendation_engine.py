"""
Unit tests and integration test for src/recommendation_engine.py.

Includes synthetic hand-verified scoring proofs, category normalization tests,
window skip logic checks, synthetic peer discovery tests, and a live integration test.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import pytest

from src.data_fetch import FundMetadata, FundNAVHistory
from src.recommendation_engine import (
    MANDATORY_DISCLAIMER,
    normalize_category_keyword,
    recommend_alternatives,
    score_fund_long_term,
    FundScore,
    RecommendationResult,
)


def test_normalize_category_keyword():
    """Verify raw AMFI category strings map cleanly to normalized category keywords."""
    assert normalize_category_keyword("Equity Scheme - Flexi Cap Fund") == "Flexi Cap"
    assert normalize_category_keyword("Equity Schemes - ELSS- Tax Saver Fund") == "ELSS"
    assert normalize_category_keyword("Equity Scheme - Mid Cap Fund") == "Mid Cap"
    assert normalize_category_keyword("Equity Scheme - Large Cap Fund") == "Large Cap"
    assert normalize_category_keyword("Equity Scheme - Small Cap Fund") == "Small Cap"
    assert normalize_category_keyword("Equity Scheme - Multi Cap Fund") == "Multi Cap"
    assert normalize_category_keyword("Equity Scheme - Large & Mid Cap Fund") == "Large & Mid Cap"
    assert normalize_category_keyword("Other Scheme - Index Funds") == "Index"
    assert normalize_category_keyword("") == "Other"


def test_score_fund_long_term_hand_verified():
    """
    Hand-verified Test Case: Multi-window rolling CAGR scoring & composite metric proof.

    SYNTHETIC DATA SETUP & ARITHMETIC PROOF:
    -----------------------------------------
    - NAV history spanning 10.5 years (2012-01-01 to 2022-07-01).
    - Constant 10% annual growth compounding: NAV(t) = 100.0 * (1.10)^years.
    - All rolling 3y, 5y, and 10y CAGRs return exactly 10.0% (0.100000).
    - Mean rolling CAGR across windows:
        3y mean = 0.10, 5y mean = 0.10, 10y mean = 0.10
    - Stdev rolling CAGR across windows: approx 0.000.
    - Risk-adjusted metric (Sharpe-like ratio on 10y window):
        (0.10 - 0.05) / (0.000 + 1e-4) = 500.0
    - Composite Score (50% return, 30% consistency, 20% risk-adjusted):
        Return Component (50%): 0.50 * (0.50*0.10 + 0.35*0.10 + 0.15*0.10) = 0.05
        Consistency Component (30%): 0.30 * (0.10 - 0.5*0.00) = 0.03
        Risk-Adjusted Component (20%): 0.20 * (500.0 * 0.05) = 5.00
        Composite Score = 0.05 + 0.03 + 5.00 = 5.08
    """
    meta = FundMetadata(100001, "Steady Flexi Cap Fund", "Steady MF", "Equity Scheme - Flexi Cap Fund", "Open Ended", "2022-07-01")
    start = date(2012, 1, 1)
    nav_dates = [start + timedelta(days=i) for i in range(3850)]

    # Generate 10% annual compounding NAV points
    nav_points = []
    for dt in nav_dates:
        yrs = (dt - start).days / 365.25
        nav_val = 100.0 * (1.10 ** yrs)
        nav_points.append((dt, nav_val))

    nav_history = FundNAVHistory(meta, nav_points)

    score = score_fund_long_term(nav_history, windows_years=[3.0, 5.0, 10.0])

    assert isinstance(score, FundScore)
    assert score.scheme_code == "100001"
    assert score.normalized_category == "Flexi Cap"
    assert score.windows_used == [3.0, 5.0, 10.0]

    assert pytest.approx(score.mean_rolling_cagr_by_window["3y"], abs=1e-3) == 0.10
    assert pytest.approx(score.mean_rolling_cagr_by_window["5y"], abs=1e-3) == 0.10
    assert pytest.approx(score.mean_rolling_cagr_by_window["10y"], abs=1e-3) == 0.10
    assert score.expense_ratio_considered is False

    assert pytest.approx(score.composite_score, abs=1e-2) == 5.08


def test_score_fund_young_fund_window_skip():
    """Verify fund with 4 years of history skips 5y and 10y windows but uses 3y window."""
    meta = FundMetadata(100002, "Young Mid Cap Fund", "Young MF", "Equity Scheme - Mid Cap Fund", "Open Ended", "2023-01-01")
    start = date(2019, 1, 1)
    nav_dates = [start + timedelta(days=i) for i in range(1460)]  # 4 years

    nav_points = [(dt, 100.0 * (1.12 ** ((dt - start).days / 365.25))) for dt in nav_dates]
    nav_history = FundNAVHistory(meta, nav_points)

    score = score_fund_long_term(nav_history, windows_years=[3.0, 5.0, 10.0])

    assert score.windows_used == [3.0]
    assert "3y" in score.mean_rolling_cagr_by_window
    assert "5y" not in score.mean_rolling_cagr_by_window
    assert "10y" not in score.mean_rolling_cagr_by_window


def test_recommend_alternatives_synthetic_universe():
    """Verify recommendation engine filters by confirmed category, ranks top N, and populates skipped_funds."""
    target_meta = FundMetadata(100, "Target Flexi Cap", "Target MF", "Equity Scheme - Flexi Cap Fund", "Open Ended", "2023-01-01")
    peer1_meta = FundMetadata(200, "Peer 1 Flexi Cap Direct Growth", "Peer MF", "Equity Scheme - Flexi Cap Fund", "Open Ended", "2023-01-01")
    peer2_meta = FundMetadata(300, "Peer 2 Flexi Cap Direct Growth", "Peer MF", "Equity Scheme - Large Cap Fund", "Open Ended", "2023-01-01")  # Wrong confirmed category!
    peer3_meta = FundMetadata(400, "Peer 3 Flexi Cap Direct Growth", "Peer MF", "Equity Scheme - Flexi Cap Fund", "Open Ended", "2023-01-01")  # Too young (<3y)

    start = date(2018, 1, 1)
    dates_5y = [start + timedelta(days=i) for i in range(1830)]

    target_nav = FundNAVHistory(target_meta, [(dt, 100.0 * (1.10 ** ((dt - start).days / 365.25))) for dt in dates_5y])
    peer1_nav = FundNAVHistory(peer1_meta, [(dt, 100.0 * (1.15 ** ((dt - start).days / 365.25))) for dt in dates_5y])
    peer2_nav = FundNAVHistory(peer2_meta, [(dt, 100.0 * (1.20 ** ((dt - start).days / 365.25))) for dt in dates_5y])

    # Peer 3 has only 1 year history
    dates_1y = [start + timedelta(days=i) for i in range(365)]
    peer3_nav = FundNAVHistory(peer3_meta, [(dt, 100.0 * (1.18 ** ((dt - start).days / 365.25))) for dt in dates_1y])

    scheme_list_sample = [
        FundMetadata(200, "Peer 1 Flexi Cap Direct Growth", "Peer MF", "Unknown", "Unknown", "2023-01-01"),
        FundMetadata(300, "Peer 2 Flexi Cap Direct Growth", "Peer MF", "Unknown", "Unknown", "2023-01-01"),
        FundMetadata(400, "Peer 3 Flexi Cap Direct Growth", "Peer MF", "Unknown", "Unknown", "2023-01-01"),
    ]

    def mock_fetch_nav(code, session=None):
        c_str = str(code)
        if c_str == "100":
            return target_nav
        elif c_str == "200":
            return peer1_nav
        elif c_str == "300":
            return peer2_nav
        elif c_str == "400":
            return peer3_nav
        raise ValueError(f"Unknown scheme {code}")

    with patch("src.recommendation_engine.fetch_fund_nav_history", side_effect=mock_fetch_nav):
        with patch("src.recommendation_engine.fetch_scheme_list", return_value=scheme_list_sample):
            res = recommend_alternatives(target_scheme_code=100, max_candidates_to_confirm=10, top_n=5)

            assert isinstance(res, RecommendationResult)
            assert res.normalized_category == "Flexi Cap"
            assert res.disclaimer == MANDATORY_DISCLAIMER
            assert res.candidates_confirmed_count == 2  # Peer 1 (Flexi Cap) + Peer 3 (Flexi Cap); Peer 2 rejected due to Large Cap mismatch

            # Peer 1 recommended (Peer 3 recorded in skipped_funds due to <3y history)
            assert len(res.recommendations) == 1
            assert res.recommendations[0].scheme_code == "200"

            assert len(res.skipped_funds) == 1
            assert res.skipped_funds[0]["scheme_code"] == "400"
            assert "insufficient history" in res.skipped_funds[0]["reason"]

            # Reasoning generated
            assert "200" in res.reasoning
            assert "Ranked #1 in Flexi Cap category" in res.reasoning["200"]


def test_recommend_alternatives_invalid_target_error():
    """Verify ValueError raised when target_scheme_code is invalid."""
    with patch("src.recommendation_engine.fetch_fund_nav_history", side_effect=ValueError("Scheme code 999 not found")):
        with pytest.raises(ValueError, match="Scheme code 999 not found"):
            recommend_alternatives(999)


@pytest.mark.integration
def test_live_recommendation_engine_integration():
    """
    Live network integration test for recommend_alternatives using real AMFI scheme code 122639 (Parag Parikh Flexi Cap).
    """
    import time
    t0 = time.time()

    res = recommend_alternatives(target_scheme_code=122639, max_candidates_to_confirm=15, top_n=3)

    elapsed = time.time() - t0

    assert isinstance(res, RecommendationResult)
    assert res.normalized_category == "Flexi Cap"
    assert res.target_score.scheme_code == "122639"
    assert res.disclaimer == MANDATORY_DISCLAIMER
    assert res.candidates_confirmed_count > 0

    print(f"\n[LIVE INTEGRATION TEST RESULTS]")
    print(f"Target Fund: {res.target_score.scheme_name} (Category: {res.normalized_category})")
    print(f"Candidates Confirmed: {res.candidates_confirmed_count}, Runtime: {elapsed:.2f}s")
    print(f"Top Recommendations Count: {len(res.recommendations)}")
    for rec in res.recommendations:
        print(f" - {rec.scheme_code} ({rec.scheme_name}): Composite Score = {rec.composite_score:.3f}")
        print(f"   Reasoning: {res.reasoning.get(rec.scheme_code)}")
