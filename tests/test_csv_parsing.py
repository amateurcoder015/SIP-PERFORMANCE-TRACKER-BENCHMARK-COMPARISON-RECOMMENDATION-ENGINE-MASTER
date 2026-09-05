"""
Unit tests for CSV transaction parser (src/data_fetch.py).
"""

from datetime import date
import io
import pytest

from src.data_fetch import parse_sip_transactions_csv, ParsedSIPTransaction


def test_parse_valid_csv_buffer_sorted_ascending():
    """Verify valid CSV is parsed into ParsedSIPTransaction objects sorted ASCENDING by date."""
    csv_content = """date,scheme_code,amount
2023-03-01,122639,1000.0
2023-01-01,122639,1000.0
2023-02-01,122639,1500.0
"""
    buffer = io.StringIO(csv_content)
    records = parse_sip_transactions_csv(buffer)

    assert len(records) == 3
    assert all(isinstance(r, ParsedSIPTransaction) for r in records)

    # Verify ASCENDING date sorting
    assert records[0].date == date(2023, 1, 1)
    assert records[0].amount == 1000.0  # Stored as POSITIVE number

    assert records[1].date == date(2023, 2, 1)
    assert records[1].amount == 1500.0

    assert records[2].date == date(2023, 3, 1)
    assert records[2].amount == 1000.0


def test_parse_csv_missing_required_columns():
    """Verify ValueError is raised listing missing required columns."""
    csv_missing_amt = """date,scheme_code
2023-01-01,122639
"""
    with pytest.raises(ValueError, match="CSV is missing required column\\(s\\): amount"):
        parse_sip_transactions_csv(io.StringIO(csv_missing_amt))

    csv_missing_all = """random_col,other_col
val1,val2
"""
    with pytest.raises(ValueError, match="CSV is missing required column\\(s\\)"):
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
