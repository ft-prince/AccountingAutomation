"""§3.4 Rule 46, §3.5 e-invoicing, §3.9 arithmetic, §3.2 heads, §3.3 rate-as-of-date."""

from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal

import pytest

from apps.gst.domain.tax import DEFAULT_RATE_TABLE
from apps.gst.domain.validators import (
    InvoiceData,
    LineData,
    ValidationIssue,
    validate_invoice,
)

D = Decimal
ON_DATE = date(2026, 6, 1)

BASE_INVOICE = InvoiceData(
    supplier_name="Unicorn Traders",
    supplier_address="1 Marine Drive, Mumbai 400001",
    supplier_gstin="27AAPFU0939F1ZV",
    serial_number="INV/2026-27/001",
    invoice_date=ON_DATE,
    recipient_name="Nexren AI",
    recipient_address="2 MG Road, Pune 411001",
    recipient_gstin="07AAGFF2194N1Z1",
    place_of_supply="27",
    is_b2b=True,
    is_reverse_charge=False,
    has_signature=True,
    irn=None,
    stated_total=D("11800"),
)

BASE_LINE = LineData(
    hsn="8471",
    description="Industrial gateway",
    quantity=D("1"),
    unit="NOS",
    unit_price=D("10000"),
    discount=D("0"),
    rate=D("18"),
    cess_rate=D("0"),
    taxable_value=D("10000"),
    cgst=D("900"),
    sgst=D("900"),
    igst=D("0"),
    cess=D("0"),
)

INTER_LINE = replace(BASE_LINE, cgst=D("0"), sgst=D("0"), igst=D("1800"))


def run(
    invoice: InvoiceData = BASE_INVOICE,
    lines: list[LineData] | None = None,
    *,
    vendor_einvoice_applicable: bool = False,
    on_date: date = ON_DATE,
) -> list[ValidationIssue]:
    return validate_invoice(
        invoice,
        [BASE_LINE] if lines is None else lines,
        vendor_einvoice_applicable=vendor_einvoice_applicable,
        rate_table=DEFAULT_RATE_TABLE,
        on_date=on_date,
    )


def codes(issues: list[ValidationIssue]) -> list[str]:
    return [issue.code for issue in issues]


# --- shape -----------------------------------------------------------------


def test_clean_intra_invoice_has_no_issues() -> None:
    assert run() == []


def test_validation_issue_is_frozen() -> None:
    issue = ValidationIssue("MISSING_FIELD", "error", "supplier_name", "missing")
    with pytest.raises(FrozenInstanceError):
        issue.code = "X"  # type: ignore[misc]


def test_inputs_are_not_mutated() -> None:
    invoice = replace(BASE_INVOICE, supplier_name="")
    lines = [replace(BASE_LINE, hsn="")]
    run(invoice, lines)
    assert invoice.supplier_name == ""
    assert lines == [replace(BASE_LINE, hsn="")]


# --- Rule 46 missing fields ------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"supplier_name": ""}, "supplier_name"),
        ({"supplier_name": "   "}, "supplier_name"),
        ({"supplier_address": ""}, "supplier_address"),
        ({"supplier_gstin": ""}, "supplier_gstin"),
        ({"serial_number": ""}, "serial_number"),
        ({"invoice_date": None}, "invoice_date"),
        ({"recipient_name": ""}, "recipient_name"),
        ({"recipient_address": ""}, "recipient_address"),
        ({"recipient_gstin": ""}, "recipient_gstin"),
        ({"place_of_supply": ""}, "place_of_supply"),
        ({"has_signature": False}, "signature"),
    ],
)
def test_missing_header_field_is_named(overrides: dict[str, object], field: str) -> None:
    issues = run(replace(BASE_INVOICE, **overrides))  # type: ignore[arg-type]
    assert len(issues) == 1
    issue = issues[0]
    assert issue.code == "MISSING_FIELD"
    assert issue.severity == "error"
    assert issue.field == field
    assert field.replace("_", " ") in issue.message


def test_recipient_gstin_not_required_for_b2c() -> None:
    assert run(replace(BASE_INVOICE, recipient_gstin="", is_b2b=False)) == []


def test_missing_supplier_gstin_does_not_also_report_gstin_invalid() -> None:
    assert codes(run(replace(BASE_INVOICE, supplier_gstin=""))) == ["MISSING_FIELD"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"hsn": ""}, "lines[0].hsn"),
        ({"description": ""}, "lines[0].description"),
        ({"unit": ""}, "lines[0].unit"),
        ({"quantity": D("0")}, "lines[0].quantity"),
        ({"quantity": D("-1")}, "lines[0].quantity"),
        ({"taxable_value": None}, "lines[0].taxable_value"),
    ],
)
def test_missing_line_field_is_named_with_index(overrides: dict[str, object], field: str) -> None:
    line = replace(BASE_LINE, **overrides)  # type: ignore[arg-type]
    issues = [i for i in run(lines=[line]) if i.code == "MISSING_FIELD"]
    assert [i.field for i in issues] == [field]


def test_line_index_follows_position() -> None:
    two_lines = replace(BASE_INVOICE, stated_total=D("23600"))
    issues = run(two_lines, [BASE_LINE, replace(BASE_LINE, hsn="")])
    assert [(i.code, i.field) for i in issues] == [("MISSING_FIELD", "lines[1].hsn")]


def test_multiple_missing_fields_all_reported_in_stable_order() -> None:
    invoice = replace(BASE_INVOICE, supplier_name="", recipient_name="", has_signature=False)
    assert [i.field for i in run(invoice)] == ["supplier_name", "recipient_name", "signature"]


# --- serial number ----------------------------------------------------------


@pytest.mark.parametrize("serial", ["INV/2026-27/001", "inv-001", "A", "1234567890123456"])
def test_valid_serial_numbers(serial: str) -> None:
    assert run(replace(BASE_INVOICE, serial_number=serial)) == []


@pytest.mark.parametrize("serial", ["12345678901234567", "INV#001", "INV 001", "INV_001", "INV.1"])
def test_invalid_serial_numbers(serial: str) -> None:
    issues = run(replace(BASE_INVOICE, serial_number=serial))
    assert codes(issues) == ["INVALID_SERIAL"]
    assert issues[0].field == "serial_number"
    assert issues[0].severity == "error"


# --- GSTIN -----------------------------------------------------------------


def test_supplier_gstin_with_bad_checksum() -> None:
    issues = run(replace(BASE_INVOICE, supplier_gstin="27AAPFU0939F1ZK"))
    assert codes(issues) == ["GSTIN_INVALID"]
    assert issues[0].field == "supplier_gstin"
    assert "checksum" in issues[0].message


def test_recipient_gstin_with_bad_checksum() -> None:
    issues = run(replace(BASE_INVOICE, recipient_gstin="07AAGFF2194N1Z2"))
    assert codes(issues) == ["GSTIN_INVALID"]
    assert issues[0].field == "recipient_gstin"


def test_supplier_in_discontinued_state_25_rejected_on_new_invoice() -> None:
    invoice = replace(BASE_INVOICE, supplier_gstin="25AAPFU0939F1ZZ", place_of_supply="25")
    assert codes(run(invoice)) == ["GSTIN_INVALID"]


def test_supplier_in_discontinued_state_25_accepted_on_historical_invoice() -> None:
    historical = date(2019, 6, 30)
    invoice = replace(
        BASE_INVOICE,
        supplier_gstin="25AAPFU0939F1ZZ",
        place_of_supply="25",
        invoice_date=historical,
    )
    assert run(invoice, on_date=historical) == []


def test_bad_supplier_gstin_skips_head_and_arithmetic_checks() -> None:
    invoice = replace(BASE_INVOICE, supplier_gstin="BAD", stated_total=D("5"))
    assert codes(run(invoice, lines=[INTER_LINE])) == ["GSTIN_INVALID"]


def test_missing_place_of_supply_skips_head_and_arithmetic_checks() -> None:
    invoice = replace(BASE_INVOICE, place_of_supply="", stated_total=D("5"))
    assert codes(run(invoice, lines=[INTER_LINE])) == ["MISSING_FIELD"]


# --- e-invoicing -------------------------------------------------------------


def test_irn_missing_is_blocking_error_when_vendor_einvoice_applies() -> None:
    issues = run(vendor_einvoice_applicable=True)
    assert len(issues) == 1
    assert issues[0].code == "IRN_MISSING"
    assert issues[0].severity == "error"
    assert issues[0].field == "irn"


def test_blank_irn_counts_as_missing() -> None:
    assert codes(run(replace(BASE_INVOICE, irn="  "), vendor_einvoice_applicable=True)) == [
        "IRN_MISSING"
    ]


def test_irn_present_satisfies_einvoice_rule() -> None:
    assert run(replace(BASE_INVOICE, irn="a" * 64), vendor_einvoice_applicable=True) == []


def test_irn_not_required_when_vendor_einvoice_does_not_apply() -> None:
    assert run(vendor_einvoice_applicable=False) == []


# --- arithmetic ------------------------------------------------------------


@pytest.mark.parametrize("stated", [D("11800"), D("11801"), D("11799"), D("11800.50")])
def test_stated_total_within_one_rupee_is_accepted(stated: Decimal) -> None:
    assert run(replace(BASE_INVOICE, stated_total=stated)) == []


@pytest.mark.parametrize("stated", [D("11801.01"), D("11798.99"), D("12000"), D("0")])
def test_stated_total_off_by_more_than_one_rupee(stated: Decimal) -> None:
    issues = run(replace(BASE_INVOICE, stated_total=stated))
    assert codes(issues) == ["ARITHMETIC_MISMATCH"]
    assert issues[0].severity == "warning"
    assert issues[0].field == "stated_total"
    assert "11800" in issues[0].message


def test_no_arithmetic_check_without_stated_total() -> None:
    assert run(replace(BASE_INVOICE, stated_total=None)) == []


def test_arithmetic_uses_computed_totals_with_round_off() -> None:
    # 100 @18 intra (118.00) + 50.25 @5 intra (52.77) + 10.53 @0 (10.53) = 181.30 -> 181
    lines = [
        replace(
            BASE_LINE,
            unit_price=D("100"),
            taxable_value=D("100"),
            cgst=D("9"),
            sgst=D("9"),
        ),
        replace(
            BASE_LINE,
            unit_price=D("50.25"),
            taxable_value=D("50.25"),
            rate=D("5"),
            cgst=D("1.26"),
            sgst=D("1.26"),
        ),
        replace(
            BASE_LINE,
            unit_price=D("10.53"),
            taxable_value=D("10.53"),
            rate=D("0"),
            cgst=D("0"),
            sgst=D("0"),
        ),
    ]
    assert run(replace(BASE_INVOICE, stated_total=D("181")), lines) == []
    assert codes(run(replace(BASE_INVOICE, stated_total=D("183")), lines)) == [
        "ARITHMETIC_MISMATCH"
    ]


# --- rate as of date ---------------------------------------------------------


def test_12_percent_valid_in_2024_invalid_in_2026() -> None:
    line = replace(BASE_LINE, rate=D("12"), cgst=D("600"), sgst=D("600"))
    invoice = replace(BASE_INVOICE, stated_total=D("11200"))
    assert (
        run(replace(invoice, invoice_date=date(2024, 6, 1)), [line], on_date=date(2024, 6, 1)) == []
    )
    issues = run(invoice, [line], on_date=date(2026, 6, 1))
    assert codes(issues) == ["RATE_INVALID_FOR_DATE"]
    assert issues[0].field == "lines[0].rate"
    assert "12" in issues[0].message and "2026-06-01" in issues[0].message


def test_tobacco_rate_checked_against_line_hsn() -> None:
    line = replace(
        BASE_LINE,
        hsn="24021010",
        rate=D("28"),
        cess_rate=D("0"),
        cgst=D("1400"),
        sgst=D("1400"),
    )
    invoice = replace(BASE_INVOICE, stated_total=D("12800"))
    assert run(invoice, [line], on_date=date(2025, 11, 1)) == []
    assert codes(run(invoice, [line], on_date=date(2026, 3, 1))) == ["RATE_INVALID_FOR_DATE"]


def test_composition_invoice_uses_composition_rates() -> None:
    line = replace(BASE_LINE, rate=D("1"), cgst=D("50"), sgst=D("50"))
    composition = replace(BASE_INVOICE, is_composition=True, stated_total=D("10100"))
    assert run(composition, [line]) == []
    regular = replace(BASE_INVOICE, stated_total=D("10100"))
    assert codes(run(regular, [line])) == ["RATE_INVALID_FOR_DATE"]


def test_restaurant_composition_5_percent() -> None:
    line = replace(BASE_LINE, hsn="9963", rate=D("5"), cgst=D("250"), sgst=D("250"))
    composition = replace(BASE_INVOICE, is_composition=True, stated_total=D("10500"))
    assert run(composition, [line]) == []


# --- tax heads vs supply type -----------------------------------------------


def test_both_heads_populated_on_one_line() -> None:
    line = replace(BASE_LINE, igst=D("1800"))
    issues = run(lines=[line])
    assert codes(issues) == ["BOTH_HEADS_POPULATED"]
    assert issues[0].field == "lines[0].tax_heads"
    assert issues[0].severity == "error"


def test_intra_invoice_with_igst_line_is_supply_type_mismatch() -> None:
    issues = run(lines=[INTER_LINE])
    assert codes(issues) == ["SUPPLY_TYPE_MISMATCH"]
    assert issues[0].field == "lines[0].tax_heads"
    assert "INTRA" in issues[0].message


def test_inter_invoice_with_cgst_sgst_line_is_supply_type_mismatch() -> None:
    inter = replace(BASE_INVOICE, place_of_supply="29")
    assert codes(run(inter, [BASE_LINE])) == ["SUPPLY_TYPE_MISMATCH"]
    assert run(inter, [INTER_LINE]) == []


def test_export_requires_igst() -> None:
    export = replace(BASE_INVOICE, place_of_supply="99", is_export=True)
    assert run(export, [INTER_LINE]) == []
    assert codes(run(export, [BASE_LINE])) == ["SUPPLY_TYPE_MISMATCH"]


def test_sez_requires_igst_even_within_same_state() -> None:
    sez = replace(BASE_INVOICE, is_sez=True)
    assert run(sez, [INTER_LINE]) == []
    assert codes(run(sez, [BASE_LINE])) == ["SUPPLY_TYPE_MISMATCH"]


def test_zero_rated_line_matches_any_supply_type() -> None:
    zero = replace(BASE_LINE, rate=D("0"), cgst=D("0"), sgst=D("0"))
    assert run(replace(BASE_INVOICE, stated_total=D("10000")), [zero]) == []
    inter = replace(BASE_INVOICE, place_of_supply="29", stated_total=D("10000"))
    assert run(inter, [zero]) == []


def test_reverse_charge_flag_passes_through_without_issues() -> None:
    rcm = replace(BASE_INVOICE, is_reverse_charge=True)
    assert rcm.is_reverse_charge is True
    assert run(rcm) == []


def test_issue_order_is_header_then_lines_then_arithmetic() -> None:
    invoice = replace(BASE_INVOICE, serial_number="BAD#", stated_total=D("1"))
    lines = [replace(BASE_LINE, hsn=""), replace(BASE_LINE, igst=D("1800"))]
    assert codes(run(invoice, lines)) == [
        "INVALID_SERIAL",
        "MISSING_FIELD",
        "BOTH_HEADS_POPULATED",
        "ARITHMETIC_MISMATCH",
    ]
