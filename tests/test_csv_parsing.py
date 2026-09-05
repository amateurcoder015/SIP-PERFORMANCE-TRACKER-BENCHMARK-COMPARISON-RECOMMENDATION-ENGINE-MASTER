"""
Unit tests for CSV transaction parser and format detector (src/data_fetch.py).
"""

from datetime import date
import io
import os
import pytest

from src.data_fetch import (
    detect_csv_format,
    parse_sip_transactions_csv,
    ParsedCSVResult,
    RawParsedTransaction,
)


def test_detect_csv_format():
    """Verify detect_csv_format identifies simple and broker_tradebook_v1 formats."""
    simple_csv = "date,scheme_code,amount\n2023-01-01,122639,1000.0\n"
    assert detect_csv_format(io.StringIO(simple_csv)) == "simple"

    tradebook_csv = "symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id\n"
    assert detect_csv_format(io.StringIO(tradebook_csv)) == "broker_tradebook_v1"

    unrecognized_csv = "col1,col2,col3\nval1,val2,val3\n"
    with pytest.raises(ValueError, match="Unrecognized CSV format. Headers:"):
        detect_csv_format(io.StringIO(unrecognized_csv))


def test_parse_valid_simple_csv_buffer():
    """Verify original simple-format CSV parses into ParsedCSVResult sorted ASCENDING by date."""
    csv_content = """date,scheme_code,amount
2023-03-01,122639,1000.0
2023-01-01,122639,1000.0
2023-02-01,122639,1500.0
"""
    buffer = io.StringIO(csv_content)
    result = parse_sip_transactions_csv(buffer)

    assert isinstance(result, ParsedCSVResult)
    records = result.transactions
    assert len(records) == 3
    assert len(result.excluded_non_buy_transactions) == 0
    assert all(isinstance(r, RawParsedTransaction) for r in records)

    # Verify ASCENDING date sorting
    assert records[0].date == date(2023, 1, 1)
    assert records[0].amount == 1000.0
    assert records[0].identifier_type == "scheme_code"
    assert records[0].identifier_value == "122639"

    assert records[1].date == date(2023, 2, 1)
    assert records[1].amount == 1500.0

    assert records[2].date == date(2023, 3, 1)
    assert records[2].amount == 1000.0


def test_parse_broker_tradebook_v1_csv_fixture():
    """
    Verify real Zerodha Console style tradebook fixture parsing:
    1. Derives amount = round(quantity * price, 2).
    2. Excludes trade_type == 'sell' into excluded_non_buy_transactions.
    3. Handles CRLF line endings and empty series columns without corruption.
    """
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "tradebook_sample.csv")
    with open(fixture_path, "rb") as f:
        result = parse_sip_transactions_csv(io.BytesIO(f.read()))

    assert isinstance(result, ParsedCSVResult)
    buy_txs = result.transactions
    sell_txs = result.excluded_non_buy_transactions

    # Fixture contains 6 total rows: 5 buy rows + 1 sell row
    assert len(buy_txs) == 5
    assert len(sell_txs) == 1

    # Verify sell row exclusion details
    assert sell_txs[0].trade_type == "sell"
    assert sell_txs[0].identifier_value == "INF966L01689"
    assert sell_txs[0].amount == 900.0  # 50.0 * 18.00

    # Verify derived amount quantity * price rounding: 100.50 * 15.25 = 1532.625 -> 1532.63
    assert buy_txs[0].date == date(2021, 1, 4)
    assert buy_txs[0].identifier_value == "INF966L01689"
    assert buy_txs[0].amount == 1532.62

    # Verify second buy row: 200.00 * 16.50 = 3300.00
    assert buy_txs[2].date == date(2021, 2, 2)
    assert buy_txs[2].identifier_value == "INF966L01689"
    assert buy_txs[2].amount == 3300.00


def test_parse_csv_missing_required_columns():
    """Verify ValueError is raised listing missing required columns."""
    csv_missing_amt = """date,scheme_code
2023-01-01,122639
"""
    with pytest.raises(ValueError, match="Unrecognized CSV format. Headers:"):
        parse_sip_transactions_csv(io.StringIO(csv_missing_amt))

    csv_missing_all = """random_col,other_col
val1,val2
"""
    with pytest.raises(ValueError, match="Unrecognized CSV format. Headers:"):
        parse_sip_transactions_csv(io.StringIO(csv_missing_all))


def test_parse_csv_invalid_date_error():
    """Verify ValueError naming row number when date format is invalid."""
    invalid_date_csv = """date,scheme_code,amount
2023-01-01,122639,1000.0
not-a-date,122639,1000.0
"""
    with pytest.raises(ValueError, match="Row 3: invalid date format 'not-a-date'"):
        parse_sip_transactions_csv(io.StringIO(invalid_date_csv))


def test_parse_csv_non_positive_amount_error():
    """Verify ValueError naming row number when amount is <= 0 or non-numeric."""
    zero_amt_csv = """date,scheme_code,amount
2023-01-01,122639,0.0
"""
    with pytest.raises(ValueError, match="Row 2: amount must be a positive number \\(> 0\\), got 0.0"):
        parse_sip_transactions_csv(io.StringIO(zero_amt_csv))

    negative_amt_csv = """date,scheme_code,amount
2023-01-01,122639,-500.0
"""
    with pytest.raises(ValueError, match="Row 2: amount must be a positive number \\(> 0\\), got -500.0"):
        parse_sip_transactions_csv(io.StringIO(negative_amt_csv))

    text_amt_csv = """date,scheme_code,amount
2023-01-01,122639,abc
"""
    with pytest.raises(ValueError, match="Row 2: amount must be a positive number \\(> 0\\), got 'abc'"):
        parse_sip_transactions_csv(io.StringIO(text_amt_csv))
