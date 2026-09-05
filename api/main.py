"""
FastAPI Backend API Layer for SIP Performance Tracker & Recommendation Engine.

Exposes endpoints for:
1. POST /api/upload-transactions — CSV upload & versatile parsing (supports Simple & Broker Tradebook formats)
2. POST /api/performance — Per-fund performance evaluation vs benchmark with identifier resolution & exception isolation
3. POST /api/recommend — Long-term peer discovery, scoring, and recommendations with mandatory disclaimer
"""

from dataclasses import asdict
from datetime import datetime, date
import io
import time
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.data_fetch import (
    fetch_benchmark_series,
    fetch_fund_nav_history,
    fetch_scheme_list,
    parse_sip_transactions_csv,
    resolve_transaction_identifiers,
    BenchmarkSeries,
    FundNAVHistory,
    ParsedCSVResult,
    ParsedSIPTransaction,
    RawParsedTransaction,
)
from src.performance_engine import evaluate_all_funds, FundPerformanceResult
from src.recommendation_engine import (
    recommend_alternatives,
    FundScore,
    RecommendationResult,
    MANDATORY_DISCLAIMER,
)


app = FastAPI(
    title="SIP Performance Tracker & Recommendation Engine API",
    description="Local backend API providing money-weighted return (XIRR), benchmark replication, and long-term peer recommendation analytics.",
    version="1.0.0",
)

# CORS configuration for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Simple In-Process Memory Cache for Fund NAV History (5-Minute TTL)
NAV_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300


def get_cached_nav_history(scheme_code: str) -> FundNAVHistory:
    """Fetch NAV history with a short in-process TTL cache to prevent redundant API calls."""
    clean_code = str(scheme_code).strip()
    now = time.time()
    if clean_code in NAV_CACHE:
        entry = NAV_CACHE[clean_code]
        if now - entry["timestamp"] < CACHE_TTL_SECONDS:
            return entry["nav_history"]

    nav_obj = fetch_fund_nav_history(clean_code)
    NAV_CACHE[clean_code] = {"timestamp": now, "nav_history": nav_obj}
    return nav_obj


# Exception Handler Mapping
@app.exception_handler(ValueError)
async def value_error_exception_handler(request, exc: ValueError):
    """Map ValueError from domain logic directly to HTTP 400 Bad Request with exact message."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Map unhandled domain/system exceptions to HTTP 500 Internal Server Error."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


# Request Models
class TransactionInputModel(BaseModel):
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    scheme_code: Optional[str] = Field(None, description="AMFI Mutual Fund Scheme Code or ISIN")
    identifier_type: Optional[str] = Field("scheme_code", description="scheme_code | isin | scheme_name")
    identifier_value: Optional[str] = Field(None, description="Raw ISIN, scheme_code, or symbol")
    scheme_name: Optional[str] = Field(None, description="Scheme Name")
    amount: float = Field(..., gt=0, description="SIP Contribution Amount (> 0)")
    trade_type: Optional[str] = Field("buy", description="buy | sell")


class PerformanceRequestModel(BaseModel):
    transactions: List[TransactionInputModel]
    benchmark_name: str = Field("NIFTY50", description="Benchmark index ticker or name (e.g. NIFTY50, SENSEX, NIFTYMIDCAP, NIFTYBANK)")
    valuation_date: Optional[str] = Field(None, description="Optional target valuation date (YYYY-MM-DD)")
    min_years_required: float = Field(1.0, ge=0.1, description="Minimum investment span required in years")


class RecommendRequestModel(BaseModel):
    target_scheme_code: str = Field(..., description="Target scheme code to compare against peers")
    max_candidates_to_confirm: int = Field(30, ge=1, le=100, description="Max pre-filtered peer candidates to confirm category")
    top_n: int = Field(5, ge=1, le=20, description="Top N peer recommendations to return")
    min_years_required: float = Field(3.0, ge=1.0, description="Minimum required NAV history span for candidate scoring")


# Helpers for JSON serialization
def _serialize_fund_performance_result(res: FundPerformanceResult) -> Dict[str, Any]:
    """Serialize FundPerformanceResult to JSON-compatible dictionary."""
    data = asdict(res)
    data["effective_valuation_date"] = res.effective_valuation_date.strftime("%Y-%m-%d")
    return data


def _serialize_fund_score(score: FundScore) -> Dict[str, Any]:
    """Serialize FundScore to JSON-compatible dictionary."""
    return asdict(score)


def _serialize_recommendation_result(res: RecommendationResult) -> Dict[str, Any]:
    """Serialize RecommendationResult to JSON-compatible dictionary, ensuring disclaimer is intact."""
    return {
        "target_score": _serialize_fund_score(res.target_score),
        "normalized_category": res.normalized_category,
        "recommendations": [_serialize_fund_score(s) for s in res.recommendations],
        "reasoning": res.reasoning,
        "skipped_funds": res.skipped_funds,
        "candidates_confirmed_count": res.candidates_confirmed_count,
        "disclaimer": res.disclaimer,
    }


# Endpoints
@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": "SIP Performance Tracker & Recommendation Engine API"}


@app.post("/api/upload-transactions")
async def upload_transactions(file: UploadFile = File(...)):
    """
    Accept CSV file upload (Simple or Broker Tradebook), parse SIP transactions, and return parse summary.
    """
    if not file.filename.endswith((".csv", ".txt")):
        raise ValueError("Uploaded file must be a CSV format (.csv file).")

    contents = await file.read()
    if not contents:
        raise ValueError("Uploaded CSV file is empty.")

    buffer = io.BytesIO(contents)
    parsed_csv_result = parse_sip_transactions_csv(buffer)

    # Group summary by identifier_value
    scheme_summary_map: Dict[str, Dict[str, Any]] = {}
    for tx in parsed_csv_result.transactions:
        id_val = str(tx.identifier_value).strip()
        if id_val not in scheme_summary_map:
            scheme_summary_map[id_val] = {
                "scheme_code": id_val if tx.identifier_type == "scheme_code" else None,
                "identifier_type": tx.identifier_type,
                "identifier_value": id_val,
                "transaction_count": 0,
                "total_amount": 0.0,
                "start_date": tx.date.strftime("%Y-%m-%d"),
                "end_date": tx.date.strftime("%Y-%m-%d"),
            }
        summary = scheme_summary_map[id_val]
        summary["transaction_count"] += 1
        summary["total_amount"] += tx.amount
        if tx.date.strftime("%Y-%m-%d") < summary["start_date"]:
            summary["start_date"] = tx.date.strftime("%Y-%m-%d")
        if tx.date.strftime("%Y-%m-%d") > summary["end_date"]:
            summary["end_date"] = tx.date.strftime("%Y-%m-%d")

    return {
        "total_transactions": len(parsed_csv_result.transactions),
        "excluded_non_buy_count": len(parsed_csv_result.excluded_non_buy_transactions),
        "schemes": list(scheme_summary_map.values()),
        "transactions": [
            {
                "date": t.date.strftime("%Y-%m-%d"),
                "amount": t.amount,
                "identifier_type": t.identifier_type,
                "identifier_value": t.identifier_value,
                "trade_type": t.trade_type,
            }
            for t in parsed_csv_result.transactions
        ],
        "excluded_transactions": [
            {
                "date": t.date.strftime("%Y-%m-%d"),
                "amount": t.amount,
                "identifier_type": t.identifier_type,
                "identifier_value": t.identifier_value,
                "trade_type": t.trade_type,
            }
            for t in parsed_csv_result.excluded_non_buy_transactions
        ],
    }


@app.post("/api/performance")
def evaluate_performance(payload: PerformanceRequestModel):
    """
    Evaluate actual fund XIRR, benchmark-equivalent XIRR, and alpha for multiple funds.
    Supports resolving ISIN identifiers via Stage 2 resolution.
    Implements per-fund exception isolation.
    """
    if not payload.transactions:
        raise ValueError("No transactions provided for performance evaluation.")

    # Convert to RawParsedTransaction list
    raw_txs: List[RawParsedTransaction] = []

    for item in payload.transactions:
        try:
            dt = datetime.strptime(item.date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid date format '{item.date}'. Expected YYYY-MM-DD.")

        # Support scheme_code or identifier_value
        if item.identifier_value:
            id_type = item.identifier_type or "isin"
            id_val = item.identifier_value
        elif item.scheme_code:
            # Check if scheme_code looks like ISIN (starts with INF)
            if item.scheme_code.startswith("INF"):
                id_type = "isin"
            else:
                id_type = "scheme_code"
            id_val = item.scheme_code
        else:
            raise ValueError(f"Transaction on {item.date} has no scheme_code or identifier_value.")

        raw_txs.append(
            RawParsedTransaction(
                date=dt,
                amount=item.amount,
                identifier_type=id_type,
                identifier_value=id_val,
                trade_type=item.trade_type or "buy",
            )
        )

    # Stage 2 Identifier Resolution
    scheme_list = fetch_scheme_list()
    resolved_domain_txs = resolve_transaction_identifiers(raw_txs, scheme_list)

    distinct_scheme_codes = set(t.scheme_code for t in resolved_domain_txs)

    # Parse optional valuation date
    val_date: Optional[date] = None
    if payload.valuation_date:
        try:
            val_date = datetime.strptime(payload.valuation_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid valuation_date format '{payload.valuation_date}'. Expected YYYY-MM-DD.")

    # Fetch benchmark index series once
    benchmark_series = fetch_benchmark_series(payload.benchmark_name)

    # Fetch fund NAV histories with per-fund exception handling
    nav_histories: Dict[str, FundNAVHistory] = {}
    fetch_errors: Dict[str, str] = {}

    for code in distinct_scheme_codes:
        try:
            nav_histories[code] = get_cached_nav_history(code)
        except Exception as exc:
            fetch_errors[code] = str(exc)

    # Evaluate funds
    evaluation_results = evaluate_all_funds(
        transactions=resolved_domain_txs,
        nav_histories=nav_histories,
        benchmark_series=benchmark_series,
        valuation_date=val_date,
        min_years_required=payload.min_years_required,
    )

    # Combine results and fetch_errors
    serialized_response: Dict[str, Any] = {}

    for code in distinct_scheme_codes:
        if code in fetch_errors:
            serialized_response[code] = {
                "scheme_code": code,
                "error": fetch_errors[code],
            }
        elif code in evaluation_results:
            res_or_exc = evaluation_results[code]
            if isinstance(res_or_exc, FundPerformanceResult):
                serialized_response[code] = _serialize_fund_performance_result(res_or_exc)
            else:
                serialized_response[code] = {
                    "scheme_code": code,
                    "error": str(res_or_exc),
                }
        else:
            serialized_response[code] = {
                "scheme_code": code,
                "error": f"No evaluation result generated for scheme {code}.",
            }

    return serialized_response


@app.post("/api/recommend")
def recommend_peers(payload: RecommendRequestModel):
    """
    Discover peer candidate funds, score long-term rolling CAGRs, and return ranked shortlist.
    Includes the mandatory, non-bypassable financial advice disclaimer verbatim.
    """
    clean_target_code = str(payload.target_scheme_code).strip()
    if not clean_target_code:
        raise ValueError("target_scheme_code cannot be empty.")

    res = recommend_alternatives(
        target_scheme_code=clean_target_code,
        max_candidates_to_confirm=payload.max_candidates_to_confirm,
        top_n=payload.top_n,
        min_years_required=payload.min_years_required,
    )

    return _serialize_recommendation_result(res)
