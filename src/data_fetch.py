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

3. Versatile Two-Stage CSV Ingestion:
   - Stage 1 (Offline Raw Parsing): detect_csv_format() distinguishes 'simple' (date, amount, scheme_code)
     and 'broker_tradebook_v1' (trade_date, isin/symbol, quantity, price) formats. Derives amount = round(qty * price, 2)
     and isolates non-buy (sell) rows into excluded_non_buy_transactions.
   - Stage 2 (Network Identifier Resolution): resolve_transaction_identifiers() maps ISINs to scheme codes using
     fetch_scheme_list() metadata with per-call caching.
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
    isin_growth: Optional[str] = None
    isin_div_reinvestment: Optional[str] = None


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
class RawParsedTransaction:
    """Raw parsed CSV transaction record prior to identifier resolution."""
    date: date
    amount: float  # Stored as POSITIVE float (> 0), derived as round(quantity * price, 2) for tradebooks
    identifier_type: str  # "scheme_code" | "isin" | "scheme_name"
    identifier_value: str
    trade_type: str = "buy"  # "buy" | "sell" | other


@dataclass
class ParsedCSVResult:
    """Container for raw parsed valid buy transactions and excluded non-buy transactions."""
    transactions: List[RawParsedTransaction]
    excluded_non_buy_transactions: List[RawParsedTransaction]


@dataclass
class ParsedSIPTransaction:
    """Resolved SIP transaction record ready for performance evaluation."""
    date: date
    scheme_code: str
    scheme_name: Optional[str]
    amount: float  # Stored as POSITIVE float (> 0)


def detect_csv_format(
    filepath_or_buffer: Union[str, io.StringIO, io.BytesIO]
) -> str:
    """
    Detect the CSV format identifier based on header columns.

    Returns "simple" or "broker_tradebook_v1".
    Raises ValueError for unrecognized formats.
    """
    try:
        if isinstance(filepath_or_buffer, (str, io.StringIO, io.BytesIO)):
            df_head = pd.read_csv(filepath_or_buffer, nrows=2)
            if hasattr(filepath_or_buffer, "seek"):
                filepath_or_buffer.seek(0)
        else:
            raise ValueError("Invalid CSV buffer or filepath.")
    except Exception as err:
        raise ValueError(f"Failed to read CSV header for format detection: {err}") from err

    cols_lower = set(str(c).strip().lower() for c in df_head.columns)

    if {"date", "amount"}.issubset(cols_lower) and ("scheme_code" in cols_lower or "scheme_name" in cols_lower):
        return "simple"
    elif {"trade_date", "quantity", "price"}.issubset(cols_lower) and ("isin" in cols_lower or "symbol" in cols_lower):
        return "broker_tradebook_v1"
    else:
        sorted_cols = sorted(list(cols_lower))
        raise ValueError(
            f"Unrecognized CSV format. Headers: {sorted_cols}. Supported formats: 'simple' (date, amount, scheme_code/scheme_name) or 'broker_tradebook_v1' (trade_date, isin/symbol, quantity, price)."
        )


def parse_sip_transactions_csv(
    filepath_or_buffer: Union[str, io.StringIO, io.BytesIO]
) -> ParsedCSVResult:
    """
    Parse and validate a SIP transaction CSV file or buffer (Stage 1 Offline Parsing).

    Parameters
    ----------
    filepath_or_buffer : Union[str, io.StringIO, io.BytesIO]
        Path to CSV file or file-like buffer.

    Returns
    -------
    ParsedCSVResult
        Parsed buy transactions and excluded non-buy (sell) transactions.
    """
    fmt = detect_csv_format(filepath_or_buffer)
    if fmt == "simple":
        return _parse_simple_csv(filepath_or_buffer)
    elif fmt == "broker_tradebook_v1":
        return _parse_broker_tradebook_v1_csv(filepath_or_buffer)
    else:
        raise ValueError(f"Unsupported CSV format '{fmt}'.")


def _parse_simple_csv(
    filepath_or_buffer: Union[str, io.StringIO, io.BytesIO]
) -> ParsedCSVResult:
    """Parse original simple-format CSV (date, amount, scheme_code/scheme_name)."""
    try:
        df = pd.read_csv(filepath_or_buffer)
    except Exception as err:
        raise ValueError(f"Failed to read CSV file or buffer: {err}") from err

    cols_lower = [str(c).strip().lower() for c in df.columns]
    col_map = {orig: lower for orig, lower in zip(df.columns, cols_lower)}
    df = df.rename(columns=col_map)

    required_base = {"date", "amount"}
    missing = required_base - set(df.columns)
    if missing or not ("scheme_code" in df.columns or "scheme_name" in df.columns):
        if not ("scheme_code" in df.columns or "scheme_name" in df.columns):
            missing.add("scheme_code/scheme_name")
        missing_sorted = sorted(list(missing))
        raise ValueError(f"CSV is missing required column(s): {', '.join(missing_sorted)}")

    transactions: List[RawParsedTransaction] = []
    excluded: List[RawParsedTransaction] = []

    for row_idx, row in df.iterrows():
        row_num = row_idx + 2

        raw_dt = row.get("date")
        if pd.isna(raw_dt) or str(raw_dt).strip() == "":
            raise ValueError(f"Row {row_num}: column 'date' is empty")
        parsed_date = _parse_date_string(str(raw_dt).strip(), row_num)

        raw_amt = row.get("amount")
        if pd.isna(raw_amt):
            raise ValueError(f"Row {row_num}: column 'amount' is empty")
        try:
            float_amt = float(raw_amt)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Row {row_num}: amount must be a positive number (> 0), got '{raw_amt}'") from err

        if float_amt <= 0:
            raise ValueError(f"Row {row_num}: amount must be a positive number (> 0), got {float_amt}")

        code_val = str(row.get("scheme_code")).strip() if "scheme_code" in df.columns and not pd.isna(row.get("scheme_code")) else ""
        name_val = str(row.get("scheme_name")).strip() if "scheme_name" in df.columns and not pd.isna(row.get("scheme_name")) else ""

        if not code_val and not name_val:
            raise ValueError(f"Row {row_num}: scheme_code and scheme_name cannot both be empty")

        if code_val:
            id_type = "scheme_code"
            id_val = code_val
        else:
            id_type = "scheme_name"
            id_val = name_val

        raw_tx = RawParsedTransaction(
            date=parsed_date,
            amount=float_amt,
            identifier_type=id_type,
            identifier_value=id_val,
            trade_type="buy",
        )
        transactions.append(raw_tx)

    transactions.sort(key=lambda x: x.date)
    return ParsedCSVResult(transactions=transactions, excluded_non_buy_transactions=excluded)


def _parse_broker_tradebook_v1_csv(
    filepath_or_buffer: Union[str, io.StringIO, io.BytesIO]
) -> ParsedCSVResult:
    """Parse Zerodha Console broker tradebook format (trade_date, isin/symbol, quantity, price, trade_type)."""
    try:
        df = pd.read_csv(filepath_or_buffer)
    except Exception as err:
        raise ValueError(f"Failed to read broker tradebook CSV: {err}") from err

    cols_lower = [str(c).strip().lower() for c in df.columns]
    col_map = {orig: lower for orig, lower in zip(df.columns, cols_lower)}
    df = df.rename(columns=col_map)

    required_base = {"trade_date", "quantity", "price"}
    missing = required_base - set(df.columns)
    if missing or not ("isin" in df.columns or "symbol" in df.columns):
        if not ("isin" in df.columns or "symbol" in df.columns):
            missing.add("isin/symbol")
        missing_sorted = sorted(list(missing))
        raise ValueError(f"Broker tradebook CSV is missing required column(s): {', '.join(missing_sorted)}")

    transactions: List[RawParsedTransaction] = []
    excluded: List[RawParsedTransaction] = []

    for row_idx, row in df.iterrows():
        row_num = row_idx + 2

        raw_dt = row.get("trade_date")
        if pd.isna(raw_dt) or str(raw_dt).strip() == "":
            raise ValueError(f"Row {row_num}: column 'trade_date' is empty")
        parsed_date = _parse_date_string(str(raw_dt).strip(), row_num)

        raw_qty = row.get("quantity")
        raw_price = row.get("price")
        if pd.isna(raw_qty) or pd.isna(raw_price):
            raise ValueError(f"Row {row_num}: quantity and price cannot be empty")
        try:
            qty = float(raw_qty)
            price = float(raw_price)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Row {row_num}: invalid quantity/price numeric values: '{raw_qty}', '{raw_price}'") from err

        if qty <= 0 or price <= 0:
            raise ValueError(f"Row {row_num}: quantity ({qty}) and price ({price}) must be positive numbers (> 0)")

        derived_amount = round(qty * price, 2)

        isin_val = str(row.get("isin")).strip() if "isin" in df.columns and not pd.isna(row.get("isin")) else ""
        symbol_val = str(row.get("symbol")).strip() if "symbol" in df.columns and not pd.isna(row.get("symbol")) else ""

        if not isin_val and not symbol_val:
            raise ValueError(f"Row {row_num}: isin and symbol cannot both be empty")

        if isin_val:
            id_type = "isin"
            id_val = isin_val
        else:
            id_type = "scheme_name"
            id_val = symbol_val

        raw_trade_type = str(row.get("trade_type", "buy")).strip().lower()

        raw_tx = RawParsedTransaction(
            date=parsed_date,
            amount=derived_amount,
            identifier_type=id_type,
            identifier_value=id_val,
            trade_type=raw_trade_type,
        )

        if raw_trade_type == "buy":
            transactions.append(raw_tx)
        else:
            excluded.append(raw_tx)

    transactions.sort(key=lambda x: x.date)
    excluded.sort(key=lambda x: x.date)
    return ParsedCSVResult(transactions=transactions, excluded_non_buy_transactions=excluded)


def resolve_transaction_identifiers(
    raw_transactions: List[RawParsedTransaction],
    scheme_list: List[FundMetadata],
    session: Optional[requests.Session] = None,
) -> List[ParsedSIPTransaction]:
    """
    Resolve RawParsedTransaction identifiers (ISIN / scheme_code) to ParsedSIPTransactions (Stage 2).

    Parameters
    ----------
    raw_transactions : List[RawParsedTransaction]
        Raw parsed transaction list.
    scheme_list : List[FundMetadata]
        Full AMFI scheme list metadata.
    session : Optional[requests.Session]
        Optional requests session.

    Returns
    -------
    List[ParsedSIPTransaction]
        Resolved transaction records with validated scheme_code and official scheme_name.
    """
    if not raw_transactions:
        return []

    # Build fast ISIN lookup map from scheme_list
    isin_map: Dict[str, FundMetadata] = {}
    for meta in scheme_list:
        if meta.isin_growth:
            isin_map[meta.isin_growth.strip().upper()] = meta
        if meta.isin_div_reinvestment:
            isin_map[meta.isin_div_reinvestment.strip().upper()] = meta

    # Per-call resolution cache so each distinct ISIN is resolved ONCE
    resolution_cache: Dict[str, FundMetadata] = {}
    resolved_records: List[ParsedSIPTransaction] = []

    for raw in raw_transactions:
        if raw.identifier_type == "scheme_code":
            clean_code = raw.identifier_value.strip()
            resolved_records.append(
                ParsedSIPTransaction(
                    date=raw.date,
                    scheme_code=clean_code,
                    scheme_name=None,
                    amount=raw.amount,
                )
            )
        elif raw.identifier_type == "isin":
            clean_isin = raw.identifier_value.strip().upper()
            if clean_isin not in resolution_cache:
                if clean_isin in isin_map:
                    resolution_cache[clean_isin] = isin_map[clean_isin]
                else:
                    raise ValueError(f"Could not resolve ISIN '{clean_isin}' to any valid AMFI scheme code.")

            matched_meta = resolution_cache[clean_isin]
            resolved_records.append(
                ParsedSIPTransaction(
                    date=raw.date,
                    scheme_code=str(matched_meta.scheme_code),
                    scheme_name=matched_meta.scheme_name,
                    amount=raw.amount,
                )
            )
        elif raw.identifier_type == "scheme_name":
            clean_name = raw.identifier_value.strip()
            matched_meta = next((m for m in scheme_list if m.scheme_name.strip() == clean_name), None)
            if not matched_meta:
                raise ValueError(f"Could not resolve scheme name '{clean_name}' to any valid AMFI scheme code.")

            resolved_records.append(
                ParsedSIPTransaction(
                    date=raw.date,
                    scheme_code=str(matched_meta.scheme_code),
                    scheme_name=matched_meta.scheme_name,
                    amount=raw.amount,
                )
            )
        else:
            raise ValueError(f"Unsupported identifier_type '{raw.identifier_type}'.")

    resolved_records.sort(key=lambda x: x.date)
    return resolved_records


def fetch_fund_nav_history(
    scheme_code: Union[int, str],
    session: Optional[requests.Session] = None,
    timeout: int = 15,
    min_api_response_points: int = 30,
) -> FundNAVHistory:
    """
    Fetch and normalize mutual fund NAV history and metadata from mfapi.in.
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
            g_isin = str(item.get("isinGrowth")).strip() if item.get("isinGrowth") else None
            d_isin = str(item.get("isinDivReinvestment")).strip() if item.get("isinDivReinvestment") else None

            schemes.append(
                FundMetadata(
                    scheme_code=code,
                    scheme_name=name,
                    fund_house="Unknown",
                    scheme_category="Unknown",
                    scheme_type="Unknown",
                    data_retrieved_at=now_iso,
                    isin_growth=g_isin,
                    isin_div_reinvestment=d_isin,
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
