"""Pure-function coverage for reconciliation/domain (100% branch per CLAUDE.md §5)."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from apps.reconciliation.domain import matching, parsers
from apps.reconciliation.domain.matching import MatchSide, classify_pair, match_records
from apps.reconciliation.domain.parsers import (
    Parse2BError,
    find_header_row,
    map_columns,
    normalise_header,
    parse_2b_json,
    parse_2b_rows,
    to_date,
    to_flag,
    to_money,
    to_pos,
)

D = Decimal
G = "27AABCT1332L1ZU"


def side(key: str, number: str, day: int, total: str = "11800", tax: str = "1800") -> MatchSide:
    return MatchSide(key, G, number, date(2026, 7, day), D(total), D(tax))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("INV-001", "INV-1"),
        ("inv 001", "INV1"),
        ("INV/0012", "INV/12"),
        ("100", "100"),
        ("00", "0"),
        ("A.B#C", "ABC"),
    ],
)
def test_normalise_invoice_number(raw: str, expected: str) -> None:
    assert matching.normalise_invoice_number(raw) == expected


def test_classify_exact_fuzzy_mismatch_none() -> None:
    record = side("r", "INV-001", 5)
    assert classify_pair(record, side("i", " inv-001 ", 5)).match_type == "exact"
    assert classify_pair(record, side("i", "INV-001", 7)).match_type == "fuzzy"
    assert classify_pair(record, side("i", "INV/001", 5)).match_type == "fuzzy"
    assert classify_pair(record, side("i", "INV-001", 5, total="11800.90")).match_type == "exact"
    mismatch = classify_pair(record, side("i", "INV-001", 5, total="11300", tax="1700"))
    assert mismatch is not None and mismatch.match_type == "value_mismatch"
    assert (mismatch.delta_value, mismatch.delta_tax) == (D("500"), D("100"))
    assert classify_pair(record, side("i", "OTHER", 9)) is None
    assert classify_pair(record, side("i", "OTHER", 5, total="5000")) is None
    other_gstin = MatchSide("i", "29AABCT1332L1ZU", "INV-001", date(2026, 7, 5), D(11800), D(1800))
    assert classify_pair(record, other_gstin) is None


def test_match_records_prefers_exact_over_stealing_fuzzy() -> None:
    # r2 is exact for i2; r1 could fuzzy-match i2 by date but must take i1 (date-only fuzzy).
    records = (side("r1", "X-9", 6), side("r2", "INV-2", 6))
    invoices = (side("i1", "INV-1", 7), side("i2", "INV-2", 6), side("i3", "INV-3", 20))
    result = match_records(records, invoices, frozenset({"i1", "i2", "i3"}))
    pairs = {p.record_key: (p.invoice_key, p.outcome.match_type) for p in result.pairs}
    assert pairs == {"r2": ("i2", "exact"), "r1": ("i1", "fuzzy")}
    assert result.missing_in_books == ()
    assert result.missing_in_2b == ("i3",)


def test_match_records_reports_missing_both_ways_and_respects_period_keys() -> None:
    records = (side("r1", "A", 1), side("r2", "B", 2))
    invoices = (side("i1", "A", 1), side("i2", "Z", 30), side("i3", "Q", 31))
    result = match_records(records, invoices, frozenset({"i1", "i2"}))
    assert [p.record_key for p in result.pairs] == ["r1"]
    assert result.missing_in_books == ("r2",)
    assert result.missing_in_2b == ("i2",)  # i3 outside the period window: not reported


def test_match_records_one_to_one_even_with_two_candidates() -> None:
    records = (side("r1", "A", 1), side("r2", "A", 1))
    invoices = (side("i1", "A", 1),)
    result = match_records(records, invoices, frozenset({"i1"}))
    assert len(result.pairs) == 1 and result.missing_in_books == ("r2",)


def test_itc_at_risk_by_type() -> None:
    assert matching.itc_at_risk("value_mismatch", D("900"), D("-90")) == D("90")
    assert matching.itc_at_risk("missing_in_books", D("900"), D("0")) == D("900")
    assert matching.itc_at_risk("exact", D("900"), D("0")) == D("0")
    assert matching.itc_at_risk("missing_in_2b", D("900"), D("0")) == D("0")


# ---- parsers -------------------------------------------------------------------------


def test_to_money_variants() -> None:
    assert to_money(None) == D("0") and to_money("") == D("0")
    assert to_money(D("1.005")) == D("1.01")
    assert to_money(11800) == D("11800.00")
    assert to_money(11800.5) == D("11800.50")
    assert to_money("₹ 1,18,000.00") == D("118000.00")
    with pytest.raises(Parse2BError):
        to_money("abc")
    with pytest.raises(Parse2BError):
        to_money(True)


def test_to_date_variants() -> None:
    assert to_date(datetime(2026, 7, 5, 10)) == date(2026, 7, 5)
    assert to_date(date(2026, 7, 5)) == date(2026, 7, 5)
    assert to_date("05-07-2026") == date(2026, 7, 5)
    assert to_date("05/07/2026") == date(2026, 7, 5)
    assert to_date("2026-07-05") == date(2026, 7, 5)
    with pytest.raises(Parse2BError):
        to_date("July 5")


def test_to_flag_and_pos() -> None:
    assert to_flag(True) is True and to_flag("y") is True and to_flag("No") is False
    assert to_pos("27-Maharashtra") == "27" and to_pos(27) == "27" and to_pos(None) == ""


def test_parse_2b_json_happy_and_errors() -> None:
    payload = {
        "data": {
            "gstin": "27AAPFU0939F1ZV",
            "rtnprd": "072026",
            "docdata": {
                "b2b": [
                    {
                        "ctin": G.lower(),
                        "trdnm": "Acme",
                        "inv": [
                            {
                                "inum": "INV-001",
                                "idt": "05-07-2026",
                                "val": 11800,
                                "pos": "27",
                                "rev": "N",
                                "itcavl": "Y",
                                "txval": 10000,
                                "igst": 0,
                                "cgst": 900,
                                "sgst": 900,
                                "cess": 0,
                            }
                        ],
                    },
                    {"ctin": "29AAA", "trdnm": None},
                ]
            },
        }
    }
    period, records = parse_2b_json(payload)
    assert period == "072026" and len(records) == 1
    rec = records[0]
    assert rec.supplier_gstin == G and rec.tax == D("1800.00") and rec.itc_available
    assert rec.invoice_date == date(2026, 7, 5) and rec.raw["inum"] == "INV-001"
    assert parse_2b_json({"data": {}}) == ("", [])
    with pytest.raises(Parse2BError):
        parse_2b_json([])
    with pytest.raises(Parse2BError):
        parse_2b_json({"data": {"docdata": {"b2b": {}}}})
    with pytest.raises(Parse2BError):
        parse_2b_json({"data": {"docdata": {"b2b": [{"ctin": G, "inv": [{"idt": "05-07-2026"}]}]}}})


HEADER = [
    "GSTIN of supplier",
    "Trade/Legal name of the Supplier",
    "Invoice number",
    "Invoice type",
    "Invoice Date",
    "Invoice Value(₹)",
    "Place of supply",
    "Supply Attract Reverse Charge",
    "Rate(%)",
    "Taxable Value (₹)",
    "Integrated Tax(₹)",
    "Central Tax(₹)",
    "State/UT Tax(₹)",
    "Cess(₹)",
    "ITC Availability",
]


def test_normalise_header_and_find_header_row() -> None:
    assert normalise_header("Invoice Value(₹)") == "invoice value"
    assert normalise_header("Taxable  Value (Rs.)") == "taxable value"
    assert normalise_header(None) == ""
    rows = [["GSTR-2B"], [], ["Goods and Services Tax"], HEADER]
    assert find_header_row(rows) == 3
    with pytest.raises(Parse2BError):
        find_header_row([["nothing"]] * 12 + [HEADER])


def test_map_columns_missing_required() -> None:
    with pytest.raises(Parse2BError, match="itc availability"):
        map_columns(HEADER[:-1])


def test_parse_2b_rows_aggregates_per_rate_and_skips_blank() -> None:
    rows = [
        ["GSTR-2B"],
        HEADER,
        [
            G,
            "Acme",
            "INV-001",
            "Regular",
            "05-07-2026",
            11800,
            "27-Maharashtra",
            "No",
            18,
            10000,
            0,
            900,
            900,
            0,
            "Yes",
        ],
        [
            G,
            "Acme",
            "INV-001",
            "Regular",
            "05-07-2026",
            11800,
            "27-Maharashtra",
            "No",
            5,
            1000,
            0,
            25,
            25,
            0,
            "No",
        ],
        [None, None, None],
        [G, "Acme", "", "Regular", "05-07-2026", 1],
        [
            G,
            "Acme",
            "INV-002",
            "Regular",
            datetime(2026, 7, 6),
            590.0,
            "27",
            "Yes",
            18,
            500,
            0,
            45,
            45,
            0,
            "Yes",
        ],
        [G, "Acme", "INV-003", "Regular", "07-07-2026", 118, "27", "No", 18, 100, 0, 9, 9],
    ]
    records = parse_2b_rows(rows)
    assert [r.invoice_number for r in records] == ["INV-001", "INV-002", "INV-003"]
    first, second, short = records
    assert short.cess == D("0") and short.itc_available is False  # columns beyond the row
    assert first.taxable_value == D("11000.00") and first.tax == D("1850.00")
    assert first.itc_available is False and first.reverse_charge is False
    assert first.invoice_value == D("11800.00") and first.place_of_supply == "27"
    assert first.raw["invoice_date"] == "05-07-2026"
    assert second.reverse_charge and second.invoice_date == date(2026, 7, 6)
    assert second.raw["invoice_date"] == "2026-07-06T00:00:00"
    assert second.raw["invoice_value"] == 590.0


def test_jsonable_decimal() -> None:
    assert parsers._jsonable(D("1.50")) == "1.50"
