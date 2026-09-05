"""
Recommendation Engine (Long-Term-Weighted Peer Comparison).

Discovers real peer mutual funds in the same AMFI category, scores them using a
long-term-weighted multi-window rolling CAGR formula (3y/5y/10y return, stdev consistency,
and risk-adjusted metrics), and returns a ranked shortlist with plain-language rationale
and mandatory financial disclaimers.

EXPENSE RATIO HANDLING DOCUMENTATION:
--------------------------------------
`expense_ratio_considered` is explicitly set to `False` in `FundScore` because `mfapi.in`
does not provide expense ratio metadata. The 50/30/20 composite weighting formula accounts
for its absence without fabricating mock proxy numbers.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import requests

from src._validators import validate_sufficient_history
from src.cagr import rolling_cagr
from src.data_fetch import fetch_fund_nav_history, fetch_scheme_list, FundMetadata, FundNAVHistory


MANDATORY_DISCLAIMER: str = (
    "DISCLAIMER: NOT FINANCIAL ADVICE. "
    "This tool provides comparative analytics based on historical mutual fund daily NAV data for personal informational use only. "
    "It is not personalized investment, financial, or tax advice, and past performance does not guarantee future results."
)


@dataclass
class FundScore:
    """Long-term performance score and metrics for a mutual fund scheme."""

    scheme_code: str
    scheme_name: str
    normalized_category: str
    windows_used: List[float]
    mean_rolling_cagr_by_window: Dict[str, float]
    stdev_rolling_cagr_by_window: Dict[str, float]
    risk_adjusted_metric: float
    composite_score: float
    expense_ratio_considered: bool = False
    data_span_years: float = 0.0


@dataclass
class RecommendationResult:
    """Ranked peer recommendation shortlist result with rationale and mandatory disclaimer."""

    target_score: FundScore
    normalized_category: str
    recommendations: List[FundScore]
    reasoning: Dict[str, str]
    skipped_funds: List[Dict[str, str]]
    candidates_confirmed_count: int
    disclaimer: str = MANDATORY_DISCLAIMER


def normalize_category_keyword(scheme_category: str) -> str:
    """
    Map raw AMFI scheme category strings to normalized keyword categories.

    Parameters
    ----------
    scheme_category : str
        Raw scheme_category string from mfapi.in metadata (e.g. "Equity Scheme - Flexi Cap Fund").

    Returns
    -------
    str
        Normalized category keyword string (e.g. "Flexi Cap", "Mid Cap", "Large Cap", "ELSS").
    """
    if not scheme_category:
        return "Other"

    raw = scheme_category.strip()
    raw_lower = raw.lower()

    if "flexi cap" in raw_lower:
        return "Flexi Cap"
    elif "large & mid cap" in raw_lower or "large and mid cap" in raw_lower:
        return "Large & Mid Cap"
    elif "mid cap" in raw_lower:
        return "Mid Cap"
    elif "large cap" in raw_lower:
        return "Large Cap"
    elif "small cap" in raw_lower:
        return "Small Cap"
    elif "elss" in raw_lower or "tax saver" in raw_lower:
        return "ELSS"
    elif "multi cap" in raw_lower:
        return "Multi Cap"
    elif "focused" in raw_lower:
        return "Focused"
    elif "index" in raw_lower or "nifty" in raw_lower or "sensex" in raw_lower:
        return "Index"
    elif "contra" in raw_lower or "value" in raw_lower:
        return "Value / Contra"

    # Fallback to stripped category string
    cleaned = raw.replace("Equity Scheme -", "").replace("Equity Schemes -", "").replace("Fund", "").strip()
    return cleaned if cleaned else "Other"


def score_fund_long_term(
    nav_history: FundNAVHistory,
    windows_years: Sequence[float] = (3.0, 5.0, 10.0),
) -> FundScore:
    """
    Score a mutual fund based on multi-window rolling CAGRs, return consistency, and risk-adjusted metric.

    Parameters
    ----------
    nav_history : FundNAVHistory
        Historical daily NAV time series for the fund.
    windows_years : Sequence[float], default (3.0, 5.0, 10.0)
        Target rolling window sizes in years.

    Returns
    -------
    FundScore
        Calculated score and metrics dataclass.

    Raises
    ------
    ValueError
        If no requested window is usable (fund history < 3.0 years).
    """
    t_min = nav_history.nav_series[0][0]
    t_max = nav_history.nav_series[-1][0]
    data_span_years = (t_max - t_min).days / 365.25

    usable_windows: List[float] = []
    mean_by_window: Dict[str, float] = {}
    stdev_by_window: Dict[str, float] = {}

    for w in sorted(windows_years):
        try:
            validate_sufficient_history(nav_history.nav_series, required_years=w)
            rolling_series = rolling_cagr(nav_history.nav_series, window_years=w)
            cagr_vals = [cagr for _, cagr in rolling_series]
            if cagr_vals:
                usable_windows.append(w)
                w_key = f"{w:g}y"
                mean_cagr = float(np.mean(cagr_vals))
                stdev_cagr = float(np.std(cagr_vals, ddof=1)) if len(cagr_vals) > 1 else 0.0
                mean_by_window[w_key] = mean_cagr
                stdev_by_window[w_key] = stdev_cagr
        except ValueError:
            # Window not satisfiable (fund too young), skip window
            continue

    if not usable_windows:
        raise ValueError(
            f"Fund scheme {nav_history.metadata.scheme_code} ({nav_history.metadata.scheme_name}) "
            f"has insufficient history for long-term scoring (data span {data_span_years:.1f} years < minimum 3.0 years required)."
        )

    # 1. Risk-adjusted metric (Sharpe-like ratio on longest usable window)
    w_longest = max(usable_windows)
    longest_key = f"{w_longest:g}y"
    mean_longest = mean_by_window[longest_key]
    stdev_longest = stdev_by_window[longest_key]

    risk_free_rate = 0.05  # 5.0% risk-free rate benchmark assumption
    risk_adjusted_metric = float((mean_longest - risk_free_rate) / (stdev_longest + 1e-4))

    # 2. Composite Score Weights over Usable Windows (50 / 30 / 20 Split)
    base_weights = {10.0: 0.50, 5.0: 0.35, 3.0: 0.15}
    sum_weights = sum(base_weights.get(w, 0.20) for w in usable_windows)
    norm_weights = {w: base_weights.get(w, 0.20) / sum_weights for w in usable_windows}

    # Return Component (50%)
    return_score = sum(norm_weights[w] * mean_by_window[f"{w:g}y"] for w in usable_windows)

    # Consistency Component (30% - lower stdev yields higher consistency contribution)
    avg_stdev = sum(norm_weights[w] * stdev_by_window[f"{w:g}y"] for w in usable_windows)
    consistency_score = max(0.0, return_score - 0.5 * avg_stdev)

    # Risk-Adjusted Component (20%)
    risk_score = max(0.0, risk_adjusted_metric * 0.05)

    # Composite Score
    composite_score = 0.50 * return_score + 0.30 * consistency_score + 0.20 * risk_score

    normalized_cat = normalize_category_keyword(nav_history.metadata.scheme_category)

    return FundScore(
        scheme_code=str(nav_history.metadata.scheme_code),
        scheme_name=nav_history.metadata.scheme_name,
        normalized_category=normalized_cat,
        windows_used=usable_windows,
        mean_rolling_cagr_by_window=mean_by_window,
        stdev_rolling_cagr_by_window=stdev_by_window,
        risk_adjusted_metric=risk_adjusted_metric,
        composite_score=composite_score,
        expense_ratio_considered=False,
        data_span_years=data_span_years,
    )


def recommend_alternatives(
    target_scheme_code: Union[int, str],
    max_candidates_to_confirm: int = 30,
    top_n: int = 5,
    min_years_required: float = 3.0,
    session: Optional[requests.Session] = None,
) -> RecommendationResult:
    """
    Discover peer funds in the same category, score them long-term, and return a ranked shortlist.

    Parameters
    ----------
    target_scheme_code : Union[int, str]
        AMFI scheme code for the target fund.
    max_candidates_to_confirm : int, default 30
        Maximum number of Phase (a) pre-filtered candidates to confirm via Phase (b) detail API calls.
    top_n : int, default 5
        Number of top-ranked peer recommendations to return.
    min_years_required : float, default 3.0
        Minimum required NAV history span for candidate scoring.
    session : Optional[requests.Session]
        Optional requests session for connection pooling or mocking.

    Returns
    -------
    RecommendationResult
        Ranked shortlist result with target score, recommendations, reasoning, skipped funds, and disclaimer.

    Raises
    ------
    ValueError
        If target_scheme_code is invalid or target fund data fetch fails.
    """
    target_code_str = str(target_scheme_code).strip()

    # 1. Fetch target fund NAV history and metadata
    target_nav = fetch_fund_nav_history(target_code_str, session=session)
    target_cat = normalize_category_keyword(target_nav.metadata.scheme_category)
    target_score = score_fund_long_term(target_nav)

    # 2. Phase (a) Cheap Name-Based Pre-Filter over Scheme List Summary
    full_scheme_list = fetch_scheme_list(session=session)

    candidate_codes: List[str] = []
    target_cat_lower = target_cat.lower()

    # Match candidate schemes containing target category keyword + Direct + Growth
    for s in full_scheme_list:
        s_code_str = str(s.scheme_code)
        if s_code_str == target_code_str:
            continue
        s_name_lower = s.scheme_name.lower()
        if target_cat_lower in s_name_lower and "direct" in s_name_lower and "growth" in s_name_lower:
            candidate_codes.append(s_code_str)

    # Fallback to broader Direct candidates if strict keyword count < max_candidates_to_confirm
    if len(candidate_codes) < max_candidates_to_confirm:
        for s in full_scheme_list:
            s_code_str = str(s.scheme_code)
            if s_code_str == target_code_str or s_code_str in candidate_codes:
                continue
            s_name_lower = s.scheme_name.lower()
            if target_cat_lower in s_name_lower and "growth" in s_name_lower:
                candidate_codes.append(s_code_str)
                if len(candidate_codes) >= max_candidates_to_confirm:
                    break

    candidate_codes = candidate_codes[:max_candidates_to_confirm]

    # 3. Phase (b) Category Confirmation & Scoring
    candidates_confirmed_count = 0
    scored_peers: List[FundScore] = []
    skipped_funds: List[Dict[str, str]] = []

    for code in candidate_codes:
        try:
            cand_nav = fetch_fund_nav_history(code, session=session)
            cand_cat = normalize_category_keyword(cand_nav.metadata.scheme_category)

            # Confirm exact category match
            if cand_cat != target_cat:
                continue

            candidates_confirmed_count += 1
            cand_score = score_fund_long_term(cand_nav)
            scored_peers.append(cand_score)
        except Exception as exc:
            skipped_funds.append({"scheme_code": code, "reason": str(exc)})

    # 4. Rank candidates by composite_score descending
    scored_peers.sort(key=lambda x: x.composite_score, reverse=True)
    top_peers = scored_peers[:top_n]

    # 5. Generate plain-language reasoning for each recommended peer
    reasoning: Dict[str, str] = {}
    for idx, peer in enumerate(top_peers, start=1):
        r_3y_peer = peer.mean_rolling_cagr_by_window.get("3y", 0.0)
        r_3y_target = target_score.mean_rolling_cagr_by_window.get("3y", 0.0)
        stdev_3y_peer = peer.stdev_rolling_cagr_by_window.get("3y", 0.0)
        stdev_3y_target = target_score.stdev_rolling_cagr_by_window.get("3y", 0.0)

        diff_return = (r_3y_peer - r_3y_target) * 100.0
        diff_stdev = (stdev_3y_target - stdev_3y_peer) * 100.0

        explanation = (
            f"Ranked #{idx} in {target_cat} category with a composite score of {peer.composite_score:.3f} "
            f"(vs target fund's {target_score.composite_score:.3f}). "
            f"Delivered a 3-year mean rolling CAGR of {r_3y_peer * 100:.1f}% ({diff_return:+.1f}% vs target) "
            f"and rolling return variance stdev of {stdev_3y_peer * 100:.1f}% ({diff_stdev:+.1f}% consistency delta vs target)."
        )
        reasoning[peer.scheme_code] = explanation

    return RecommendationResult(
        target_score=target_score,
        normalized_category=target_cat,
        recommendations=top_peers,
        reasoning=reasoning,
        skipped_funds=skipped_funds,
        candidates_confirmed_count=candidates_confirmed_count,
        disclaimer=MANDATORY_DISCLAIMER,
    )
