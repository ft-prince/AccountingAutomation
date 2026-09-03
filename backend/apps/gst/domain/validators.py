"""Invoice validation (PROJECT_SPECS §3.4 Rule 46, §3.5 e-invoicing, §3.9 arithmetic).

Returns a stable, ordered list of ValidationIssue values; never raises on bad data.
Order: header issues, then per-line issues, then the invoice-level arithmetic check.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from apps.gst.domain.gstin import validate as validate_gstin
from apps.gst.domain.supply import SupplyType, determine_supply_type
from apps.gst.domain.tax import (
    TaxRate,
    compute_invoice_totals,
    compute_line,
    rate_valid_on,
)

Severity = Literal["error", "warning"]

SERIAL_MAX_LENGTH = 16
SERIAL_PATTERN = re.compile(r"^[A-Za-z0-9/-]{1,16}$")
ARITHMETIC_TOLERANCE = Decimal("1")
GSTIN_STATE_LENGTH = 2

MISSING_FIELD = "MISSING_FIELD"
INVALID_SERIAL = "INVALID_SERIAL"
GSTIN_INVALID = "GSTIN_INVALID"
IRN_MISSING = "IRN_MISSING"
ARITHMETIC_MISMATCH = "ARITHMETIC_MISMATCH"
RATE_INVALID_FOR_DATE = "RATE_INVALID_FOR_DATE"
BOTH_HEADS_POPULATED = "BOTH_HEADS_POPULATED"
SUPPLY_TYPE_MISMATCH = "SUPPLY_TYPE_MISMATCH"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    field: str
    message: str


@dataclass(frozen=True)
class InvoiceData:
    supplier_name: str
    supplier_address: str
    supplier_gstin: str
    serial_number: str
    invoice_date: date | None
    recipient_name: str
    recipient_address: str
    recipient_gstin: str
    place_of_supply: str
    is_b2b: bool
    is_reverse_charge: bool
    has_signature: bool
    irn: str | None
    stated_total: Decimal | None
    is_export: bool = False
    is_sez: bool = False
    is_composition: bool = False


@dataclass(frozen=True)
class LineData:
    hsn: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    discount: Decimal
    rate: Decimal
    cess_rate: Decimal
    taxable_value: Decimal | None
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal


def _missing(field: str) -> ValidationIssue:
    label = field.replace("_", " ")
    return ValidationIssue(MISSING_FIELD, "error", field, f"Rule 46: {label} is missing")


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def validate_invoice(
    inv: InvoiceData,
    lines: list[LineData],
    *,
    vendor_einvoice_applicable: bool,
    rate_table: tuple[TaxRate, ...],
    on_date: date,
) -> list[ValidationIssue]:
    """Run every §3 check against an invoice as of `on_date` (normally the invoice date)."""
    supply_type = _supply_type_for(inv)
    line_issues = [
        issue
        for index, line in enumerate(lines)
        for issue in _validate_line(index, line, supply_type, inv, rate_table, on_date)
    ]
    return [
        *_header_issues(inv, on_date),
        *_einvoice_issues(inv, vendor_einvoice_applicable),
        *line_issues,
        *_arithmetic_issues(inv, lines, supply_type),
    ]


def _supply_type_for(inv: InvoiceData) -> SupplyType | None:
    """None when the supplier GSTIN or place of supply is unusable; head checks are skipped."""
    if not validate_gstin(inv.supplier_gstin).is_valid or _is_blank(inv.place_of_supply):
        return None
    return determine_supply_type(
        inv.supplier_gstin[:GSTIN_STATE_LENGTH],
        inv.place_of_supply,
        is_export=inv.is_export,
        is_sez=inv.is_sez,
    )


def _header_issues(inv: InvoiceData, on_date: date) -> list[ValidationIssue]:
    required: list[tuple[str, bool]] = [
        ("supplier_name", _is_blank(inv.supplier_name)),
        ("supplier_address", _is_blank(inv.supplier_address)),
        ("supplier_gstin", _is_blank(inv.supplier_gstin)),
        ("serial_number", _is_blank(inv.serial_number)),
        ("invoice_date", inv.invoice_date is None),
        ("recipient_name", _is_blank(inv.recipient_name)),
        ("recipient_address", _is_blank(inv.recipient_address)),
        ("recipient_gstin", inv.is_b2b and _is_blank(inv.recipient_gstin)),
        ("place_of_supply", _is_blank(inv.place_of_supply)),
        ("signature", not inv.has_signature),
    ]
    return [
        *(_missing(field) for field, is_missing in required if is_missing),
        *_serial_issues(inv.serial_number),
        *_gstin_issues("supplier_gstin", inv.supplier_gstin, on_date),
        *_gstin_issues("recipient_gstin", inv.recipient_gstin, on_date),
    ]


def _serial_issues(serial: str) -> list[ValidationIssue]:
    if _is_blank(serial) or SERIAL_PATTERN.match(serial):
        return []
    return [
        ValidationIssue(
            INVALID_SERIAL,
            "error",
            "serial_number",
            f"Rule 46: serial {serial!r} must be 1-{SERIAL_MAX_LENGTH} chars of A-Z, 0-9, / and -",
        )
    ]


def _gstin_issues(field: str, gstin: str, on_date: date) -> list[ValidationIssue]:
    if _is_blank(gstin):
        return []
    result = validate_gstin(gstin, on_date)
    if result.is_valid:
        return []
    return [ValidationIssue(GSTIN_INVALID, "error", field, "; ".join(result.errors))]


def _einvoice_issues(inv: InvoiceData, vendor_einvoice_applicable: bool) -> list[ValidationIssue]:
    if not vendor_einvoice_applicable or not _is_blank(inv.irn):
        return []
    return [
        ValidationIssue(
            IRN_MISSING,
            "error",
            "irn",
            "e-invoicing applies to this vendor and no IRN is present; ITC is at risk",
        )
    ]


def _validate_line(
    index: int,
    line: LineData,
    supply_type: SupplyType | None,
    inv: InvoiceData,
    rate_table: tuple[TaxRate, ...],
    on_date: date,
) -> list[ValidationIssue]:
    prefix = f"lines[{index}]"
    required: list[tuple[str, bool]] = [
        ("hsn", _is_blank(line.hsn)),
        ("description", _is_blank(line.description)),
        ("quantity", line.quantity <= 0),
        ("unit", _is_blank(line.unit)),
        ("taxable_value", line.taxable_value is None),
    ]
    return [
        *(_missing(f"{prefix}.{field}") for field, is_missing in required if is_missing),
        *_rate_issues(prefix, line, inv.is_composition, rate_table, on_date),
        *_head_issues(prefix, line, supply_type),
    ]


def _rate_issues(
    prefix: str,
    line: LineData,
    is_composition: bool,
    rate_table: tuple[TaxRate, ...],
    on_date: date,
) -> list[ValidationIssue]:
    hsn = None if _is_blank(line.hsn) else line.hsn
    if rate_valid_on(line.rate, on_date, rate_table, hsn, is_composition=is_composition):
        return []
    return [
        ValidationIssue(
            RATE_INVALID_FOR_DATE,
            "error",
            f"{prefix}.rate",
            f"rate {line.rate}% is not in the slab table as of {on_date.isoformat()}",
        )
    ]


def _head_issues(
    prefix: str, line: LineData, supply_type: SupplyType | None
) -> list[ValidationIssue]:
    field = f"{prefix}.tax_heads"
    has_igst = line.igst > 0
    has_cgst_sgst = line.cgst > 0 or line.sgst > 0
    if has_igst and has_cgst_sgst:
        return [
            ValidationIssue(
                BOTH_HEADS_POPULATED,
                "error",
                field,
                "IGST and CGST/SGST are both populated on one line",
            )
        ]
    if supply_type is None:
        return []
    is_mismatch = has_igst if supply_type is SupplyType.INTRA else has_cgst_sgst
    if not is_mismatch:
        return []
    expected = "IGST" if supply_type.uses_igst else "CGST/SGST"
    return [
        ValidationIssue(
            SUPPLY_TYPE_MISMATCH,
            "error",
            field,
            f"supply type {supply_type.name} expects {expected} only",
        )
    ]


def _arithmetic_issues(
    inv: InvoiceData, lines: list[LineData], supply_type: SupplyType | None
) -> list[ValidationIssue]:
    if inv.stated_total is None or supply_type is None:
        return []
    computed = compute_invoice_totals(
        [
            compute_line(
                line.unit_price,
                line.quantity,
                line.discount,
                line.rate,
                line.cess_rate,
                supply_type,
            )
            for line in lines
        ]
    )
    if abs(computed.total - inv.stated_total) <= ARITHMETIC_TOLERANCE:
        return []
    return [
        ValidationIssue(
            ARITHMETIC_MISMATCH,
            "warning",
            "stated_total",
            f"computed total {computed.total} differs from stated total {inv.stated_total} "
            f"by more than {ARITHMETIC_TOLERANCE}",
        )
    ]
