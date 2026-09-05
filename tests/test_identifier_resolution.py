"""
Unit tests and integration test for Stage 2 Identifier Resolution (src/data_fetch.py).
"""

from datetime import date
import io
import os
import pytest

from src.data_fetch import (
    fetch_scheme_list,
    parse_sip_transactions_csv,
    resolve_transaction_identifiers,
    FundMetadata,
    ParsedSIPTransaction,
    RawParsedTransaction,
)


def test_resolve_transaction_identifiers_mocked():
    """Verify ISIN resolution maps to scheme_code and reuses per-call lookup cache."""
    scheme_list = [
        FundMetadata(
            scheme_code=120828,
            scheme_name="Quant Small Cap Fund - Direct Plan - Growth Option",
            fund_house="Quant Mutual Fund",
            scheme_category="Equity Scheme - Small Cap Fund",
            scheme_type="Open Ended Schemes",
            data_retrieved_at="2022-01-01",
            isin_growth="INF966L01689",
            isin_div_reinvestment=None,
        ),
        FundMetadata(
            scheme_code=122639,
            scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
            fund_house="PPFAS Mutual Fund",
            scheme_category="Equity Scheme - Flexi Cap Fund",
            scheme_type="Open Ended Schemes",
            data_retrieved_at="2022-01-01",
            isin_growth="INF879O01015",
            isin_div_reinvestment=None,
        ),
    ]

    # 3 raw transactions with the SAME ISIN + 1 simple scheme_code transaction
    raw_txs = [
        RawParsedTransaction(date(2021, 1, 4), 1000.0, "isin", "INF966L01689", "buy"),
        RawParsedTransaction(date(2021, 2, 2), 2000.0, "isin", "INF966L01689", "buy"),
        RawParsedTransaction(date(2021, 3, 1), 1500.0, "isin", "INF966L01689", "buy"),
        RawParsedTransaction(date(2021, 4, 1), 3000.0, "scheme_code", "122639", "buy"),
    ]

    resolved = resolve_transaction_identifiers(raw_txs, scheme_list)

    assert len(resolved) == 4
    assert all(isinstance(r, ParsedSIPTransaction) for r in resolved)

    # First 3 resolved to Quant Small Cap (120828)
    for i in range(3):
        assert resolved[i].scheme_code == "120828"
        assert resolved[i].scheme_name == "Quant Small Cap Fund - Direct Plan - Growth Option"

    # 4th transaction passed through scheme_code 122639 directly
    assert resolved[3].scheme_code == "122639"


def test_unresolvable_isin_error():
    """Verify ValueError is raised naming the specific unresolvable ISIN."""
    scheme_list = [
        FundMetadata(100, "Dummy Fund", "House", "Cat", "Type", "2022-01-01", isin_growth="INF111111111")
    ]
    raw_txs = [RawParsedTransaction(date(2021, 1, 1), 1000.0, "isin", "INF000000000", "buy")]

    with pytest.raises(ValueError, match="Could not resolve ISIN 'INF000000000'"):
        resolve_transaction_identifiers(raw_txs, scheme_list)


def test_scheme_code_passthrough_regression():
    """Regression test: raw transaction with scheme_code passes through unmodified."""
    scheme_list = []
    raw_txs = [RawParsedTransaction(date(2021, 1, 1), 1000.0, "scheme_code", "122639", "buy")]

    resolved = resolve_transaction_identifiers(raw_txs, scheme_list)
    assert len(resolved) == 1
    assert resolved[0].scheme_code == "122639"
    assert resolved[0].amount == 1000.0


@pytest.mark.integration
def test_live_tradebook_isin_resolution_integration():
    """
    Live network integration test: parse real tradebook CSV fixture and resolve all 4 real ISINs against live fetch_scheme_list().
    """
    import time
    t0 = time.time()

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "tradebook_sample.csv")
    with open(fixture_path, "rb") as f:
        parsed_csv = parse_sip_transactions_csv(io.BytesIO(f.read()))

    live_scheme_list = fetch_scheme_list()
    resolved = resolve_transaction_identifiers(parsed_csv.transactions, live_scheme_list)
    elapsed = time.time() - t0

    assert len(resolved) == 5  # 5 buy transactions resolved

    # Extract resolved scheme codes map per ISIN
    resolved_codes = {}
    for tx in resolved:
        resolved_codes[tx.scheme_code] = tx.scheme_name

    print("\n[LIVE ISIN RESOLUTION INTEGRATION TEST RESULTS]")
    print(f"Total schemes fetched in list: {len(live_scheme_list)}, Runtime: {elapsed:.2f}s")
    print(f"Resolved Buy Transactions Count: {len(resolved)}")
    print("Resolved Target Scheme Codes:")
    for code, name in resolved_codes.items():
        print(f" - Scheme Code {code}: {name}")

    # Assert exact scheme_codes found in Step 0.4
    assert "120828" in resolved_codes  # INF966L01689 (Quant Small Cap)
    assert "130498" in resolved_codes  # INF179KA1RQ7 (HDFC Large & Mid Cap)
    assert "120166" in resolved_codes  # INF174K01LS2 (Kotak Flexi Cap)
    assert "118663" in resolved_codes  # INF204K01YC4 (Nippon India Gold Savings)
