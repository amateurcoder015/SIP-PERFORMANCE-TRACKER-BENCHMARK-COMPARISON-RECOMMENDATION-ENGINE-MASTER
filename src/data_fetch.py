"""
Data Layer Module for Mutual Fund NAVs, Benchmark Indices, and SIP CSV Transactions.

CONVENTIONS & DATA CONTRACTS:
-----------------------------
1. NAV & Benchmark Series Ordering:
   All NAV series (FundNAVHistory.nav_series) and benchmark index series (BenchmarkSeries.level_series)
   are explicitly normalized and returned in ASCENDING order by date (oldest -> newest).
   This satisfies Step 1 core math module expectations.

2. SIP Transaction Amount Sign:
   ParsedSIPTransaction.amount stores contribution amounts as POSITIVE numbers (> 0) representing
   raw user input from CSV. The negative sign flip (< 0) required by Step 1's calculate_xirr()
   is performed at cashflow assembly in Step 3, NOT inside this module.
"""

from dataclasses import dataclass
from datetime import datetime, date, timezone
import io
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import requests
import yfinance as yf

from src._validators import validate_nav_series


MFAPI_BASE_URL = "https://api.mfapi.in/mf"

# Internal lookup map for supported Indian benchmark index tickers
BENCHMARK_TICKER_MAP: Dict[str, str] = {
    "NIFTY50": "^NSEI",
    "NIFTY 50": "^NSEI",
    "NIFTY_50": "^NSEI",
    "^NSEI": "^NSEI",
    "SENSEX": "^BSESN",
    "BSE SENSEX": "^BSESN",
    "S&P BSE SENSEX": "^BSESN",
    "^BSESN": "^BSESN",
    "NIFTYMIDCAP": "^NSMIDCP",
    "NIFTY MIDCAP 100": "^NSMIDCP",
    "NIFTY_MIDCAP_100": "^NSMIDCP",
    "^NSMIDCP": "^NSMIDCP",
    "NIFTYBANK": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY_BANK": "^NSEBANK",
    "^NSEBANK": "^NSEBANK",
}


@dataclass
class FundMetadata:
    """Metadata for an Indian Mutual Fund Scheme."""
    scheme_code: int
    scheme_name: str
    fund_house: str
    scheme_category: str
    scheme_type: str
    data_retrieved_at: str


@dataclass
class FundNAVHistory:
    """Historical daily NAV time series for a mutual fund scheme."""
    metadata: FundMetadata
    nav_series: List[Tuple[date, float]]  # Strictly ASCENDING by date


@dataclass
class BenchmarkSeries:
    """Historical daily closing index levels for a benchmark index."""
    benchmark_name: str
    ticker: str
    level_series: List[Tuple[date, float]]  # Strictly ASCENDING by date
    data_retrieved_at: str


@dataclass
class ParsedSIPTransaction:
    """Raw parsed SIP transaction record from CSV."""
    date: date
    scheme_code: str
    scheme_name: Optional[str]
    amount: float  # Stored as POSITIVE float (> 0)


def parse_sip_transactions_csv(
    filepath_or_buffer: Union[str, io.StringIO, io.BytesIO]
) -> List[ParsedSIPTransaction]:
    """
    Parse and validate a SIP transaction CSV file or buffer.

    Expected CSV columns: `date`, `amount`, and `scheme_code` or `scheme_name`.

    Parameters
    ----------
    filepath_or_buffer : Union[str, io.StringIO, io.BytesIO]
        Path to CSV file or file-like buffer.

    Returns
    -------
    List[ParsedSIPTransaction]
        Parsed transaction records sorted ASCENDING by date.

    Raises
    ------
    ValueError
        If required columns are missing, dates are invalid, or amounts are <= 0.
    """
    try:
        df = pd.read_csv(filepath_or_buffer)
    except Exception as err:
        raise ValueError(f"Failed to read CSV file or buffer: {err}") from err

    # Normalize column names to lowercase stripped strings
    cols_lower = [str(c).strip().lower() for c in df.columns]
    col_map = {orig: lower for orig, lower in zip(df.columns, cols_lower)}
    df = df.rename(columns=col_map)

    # Check required columns
    required_base = {"date", "amount"}
    missing = required_base - set(df.columns)
    if missing or not ("scheme_code" in df.columns or "scheme_name" in df.columns):
        if not ("scheme_code" in df.columns or "scheme_name" in df.columns):
            missing.add("scheme_code/scheme_name")
        missing_sorted = sorted(list(missing))
        raise ValueError(f"CSV is missing required column(s): {', '.join(missing_sorted)}")

    parsed_records: List[ParsedSIPTransaction] = []

    for row_idx, row in df.iterrows():
        row_num = row_idx + 2  # 1-indexed accounting for CSV header row

        # Parse date
        raw_dt = row.get("date")
        if pd.isna(raw_dt) or str(raw_dt).strip() == "":
            raise ValueError(f"Row {row_num}: column 'date' is empty")

        parsed_date = _parse_date_string(str(raw_dt).strip(), row_num)

        # Parse amount
        raw_amt = row.get("amount")
        if pd.isna(raw_amt):
            raise ValueError(f"Row {row_num}: column 'amount' is empty")

        try:
            float_amt = float(raw_amt)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Row {row_num}: amount must be a positive number (> 0), got '{raw_amt}'") from err

        if float_amt <= 0:
            raise ValueError(f"Row {row_num}: amount must be a positive number (> 0), got {float_amt}")

        # Parse scheme_code / scheme_name
        code_val = str(row.get("scheme_code")).strip() if "scheme_code" in df.columns and not pd.isna(row.get("scheme_code")) else ""
        name_val = str(row.get("scheme_name")).strip() if "scheme_name" in df.columns and not pd.isna(row.get("scheme_name")) else None

        if not code_val and not name_val:
            raise ValueError(f"Row {row_num}: scheme_code and scheme_name cannot both be empty")

        primary_code = code_val if code_val else (name_val or "")

        parsed_records.append(
            ParsedSIPTransaction(
                date=parsed_date,
                scheme_code=primary_code,
                scheme_name=name_val,
                amount=float_amt,
            )
        )

    # Sort ascending by date
    parsed_records.sort(key=lambda x: x.date)
    return parsed_records


def fetch_fund_nav_history(
    scheme_code: Union[int, str],
    session: Optional[requests.Session] = None,
    timeout: int = 15,
    min_api_response_points: int = 30,
) -> FundNAVHistory:
    """
    Fetch and normalize mutual fund NAV history and metadata from mfapi.in.

    Parameters
    ----------
    scheme_code : Union[int, str]
        AMFI scheme code.
    session : Optional[requests.Session]
        Optional requests session for mocking or connection pooling.
    timeout : int, default 15
        Request timeout in seconds.
    min_api_response_points : int, default 30
        Minimum low-level API sanity threshold to reject empty or corrupted API payloads.
        (Note: Financial span sufficiency e.g. 1y/3y/5y CAGR is validated separately by
        validate_sufficient_history).

    Returns
    -------
    FundNAVHistory
        Normalized fund NAV history object with ASCENDING nav_series.

    Raises
    ------
    ValueError
        If scheme_code is invalid, scheme not found, or NAV payload has < min_api_response_points.
    """
    clean_code = str(scheme_code).strip()
    url = f"{MFAPI_BASE_URL}/{clean_code}"

    client = session or requests
    try:
        res = client.get(url, timeout=timeout)
        if res.status_code == 404:
            raise ValueError(f"Scheme code '{clean_code}' not found on mfapi.in API.")
        res.raise_for_status()
        payload = res.json()
    except requests.exceptions.RequestException as err:
        raise ValueError(f"Failed to fetch mutual fund NAV data for scheme '{clean_code}': {err}") from err

    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        raise ValueError(f"Scheme code '{clean_code}' not found or returned invalid status on mfapi.in API.")

    meta_raw = payload.get("meta", {})
    raw_data = payload.get("data", [])

    if not raw_data:
        raise ValueError(f"Scheme code '{clean_code}' returned no NAV history data.")

    nav_points: List[Tuple[date, float]] = []
    for item in raw_data:
        dt_str = item.get("date")
        nav_str = item.get("nav")
        if dt_str and nav_str:
            try:
                dt = datetime.strptime(dt_str, "%d-%m-%Y").date()
                nav_val = float(nav_str)
                if nav_val > 0:
                    nav_points.append((dt, nav_val))
            except (ValueError, TypeError):
                continue

    if len(nav_points) < min_api_response_points:
        raise ValueError(
            f"Scheme '{clean_code}' returned corrupt/insufficient API payload ({len(nav_points)} points < {min_api_response_points} min API sanity threshold)."
        )

    # Sort ascending by date (since mfapi.in delivers descending order)
    validated_nav = validate_nav_series(nav_points)

    now_iso = datetime.now(timezone.utc).isoformat()
    metadata = FundMetadata(
        scheme_code=int(meta_raw.get("scheme_code", clean_code)),
        scheme_name=meta_raw.get("scheme_name", f"Scheme {clean_code}"),
        fund_house=meta_raw.get("fund_house", "Unknown Fund House"),
        scheme_category=meta_raw.get("scheme_category", "Unknown Category"),
        scheme_type=meta_raw.get("scheme_type", "Unknown Type"),
        data_retrieved_at=now_iso,
    )

    return FundNAVHistory(metadata=metadata, nav_series=validated_nav)


def fetch_scheme_list(
    session: Optional[requests.Session] = None,
    timeout: int = 15,
) -> List[FundMetadata]:
    """
    Fetch full AMFI mutual fund scheme list from mfapi.in.

    Returns
    -------
    List[FundMetadata]
        List of scheme metadata summaries.
    """
    client = session or requests
    try:
        res = client.get(MFAPI_BASE_URL, timeout=timeout)
        res.raise_for_status()
        payload = res.json()
    except requests.exceptions.RequestException as err:
        raise ValueError(f"Failed to fetch scheme list from mfapi.in: {err}") from err

    if not isinstance(payload, list):
        raise ValueError("Invalid scheme list response format from mfapi.in API.")

    now_iso = datetime.now(timezone.utc).isoformat()
    schemes: List[FundMetadata] = []

    for item in payload:
        try:
            code = int(item.get("schemeCode"))
            name = str(item.get("schemeName"))
            schemes.append(
                FundMetadata(
                    scheme_code=code,
                    scheme_name=name,
                    fund_house="Unknown",
                    scheme_category="Unknown",
                    scheme_type="Unknown",
                    data_retrieved_at=now_iso,
                )
            )
        except (ValueError, TypeError):
            continue

    return schemes


def fetch_benchmark_series(
    benchmark_name: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> BenchmarkSeries:
    """
    Fetch historical daily benchmark closing prices using yfinance.

    Parameters
    ----------
    benchmark_name : str
        Benchmark name or symbol (e.g. "NIFTY50", "SENSEX", "NIFTYMIDCAP", "NIFTYBANK").
    start_date : Optional[date]
        Requested start date.
    end_date : Optional[date]
        Requested end date.

    Returns
    -------
    BenchmarkSeries
        Benchmark series with ASCENDING level_series.

    Raises
    ------
    ValueError
        If benchmark_name is unsupported or requested range precedes available data.
    """
    normalized_name = benchmark_name.strip().upper()
    ticker = BENCHMARK_TICKER_MAP.get(normalized_name)

    if not ticker:
        supported_list = "NIFTY50 (^NSEI), SENSEX (^BSESN), NIFTYMIDCAP (^NSMIDCP), NIFTYBANK (^NSEBANK)"
        raise ValueError(
            f"Unsupported benchmark name '{benchmark_name}'. Supported benchmarks: {supported_list}"
        )

    try:
        ticker_obj = yf.Ticker(ticker)
        if start_date and end_date:
            df = ticker_obj.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=(end_date + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
            )
        else:
            df = ticker_obj.history(period="max")
    except Exception as err:
        raise ValueError(f"Failed to fetch benchmark history for '{benchmark_name}' ({ticker}): {err}") from err

    if df.empty or "Close" not in df.columns:
        raise ValueError(f"No index level data returned for benchmark '{benchmark_name}' ({ticker}).")

    series: List[Tuple[date, float]] = []
    for index_val, row in df.iterrows():
        try:
            dt = index_val.date() if hasattr(index_val, "date") else index_val
            close_price = float(row["Close"])
            if close_price > 0:
                series.append((dt, close_price))
        except (ValueError, TypeError, KeyError):
            continue

    if not series:
        raise ValueError(f"Could not parse valid positive index levels for benchmark '{benchmark_name}'.")

    validated_series = validate_nav_series(series)
    earliest_available_date = validated_series[0][0]

    if start_date and start_date < earliest_available_date:
        raise ValueError(
            f"Requested start date {start_date} is earlier than earliest available benchmark history date {earliest_available_date} for benchmark '{benchmark_name}'."
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    return BenchmarkSeries(
        benchmark_name=benchmark_name,
        ticker=ticker,
        level_series=validated_series,
        data_retrieved_at=now_iso,
    )


def _parse_date_string(date_str: str, row_num: int) -> date:
    """Parse common date formats."""
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Row {row_num}: invalid date format '{date_str}' in column 'date'")
