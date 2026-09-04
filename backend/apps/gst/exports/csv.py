"""Accounting-package CSV exports: Tally import CSV, Zoho Books import CSV, raw dump.

Tally XML is out of scope for v1 — this is the flat CSV Tally's import templates accept.
Every export is confirmed-only (§7.1); the needs_review count for the same range is
returned separately so the caller can put it in the X-Pending-Count header.
Money is written as Decimal strings with 2 dp; nothing here touches float.
"""

import csv
import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.gst.domain.periods import fy_bounds, fy_for_date
from apps.gst.exports.common import ExportError, rate_number
from apps.invoices.models import Direction, Invoice, InvoiceLine, InvoiceStatus, SupplyKind

TALLY_DATE_FORMAT = "%d-%m-%Y"
TALLY_COLUMNS = (
    "Date",
    "Voucher Type",
    "Party Ledger",
    "Ledger",
    "Amount",
    "CGST",
    "SGST",
    "IGST",
    "Narration",
    "Invoice No",
)
TALLY_VOUCHER = {Direction.OUTWARD: "Sales", Direction.INWARD: "Purchase"}
ZOHO_COLUMNS = (
    "Invoice Date",
    "Invoice Number",
    "Customer Name",
    "GST Treatment",
    "GSTIN",
    "Place of Supply",
    "Item Name",
    "HSN/SAC",
    "Quantity",
    "Rate",
    "Tax Name",
    "Tax Percentage",
    "Total",
)
# Zoho Books GST treatment codes; inward rows reuse the same columns (Zoho's bill import
# maps "Customer Name" to the vendor column on upload — noted in the export filename).
ZOHO_TREATMENT_EXPORT = "overseas"
ZOHO_TREATMENT_SEZ = "business_sez"
ZOHO_TREATMENT_COMPOSITION = "business_composition"
ZOHO_TREATMENT_REGISTERED = "business_gst"
ZOHO_TREATMENT_UNREGISTERED = "business_none"


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


def date_range_from_params(params: dict[str, str], today: date | None = None) -> DateRange:
    """fy= defaults to the current FY; from=/to= (ISO) narrow or override it."""
    today = today or date.today()
    try:
        start, end = fy_bounds(params.get("fy") or fy_for_date(today))
        if v := params.get("from"):
            start = date.fromisoformat(v)
        if v := params.get("to"):
            end = date.fromisoformat(v)
    except ValueError as exc:
        raise ExportError(str(exc)) from exc
    if start > end:
        raise ExportError("from must be on or before to")
    return DateRange(start, end)


def confirmed_in_range(org: Any, rng: DateRange) -> QuerySet[Invoice]:
    return (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED, invoice_date__range=(rng.start, rng.end))
        .select_related("party", "gstin_profile")
        .prefetch_related("lines__category")
        .order_by("invoice_date", "invoice_number")
    )


def pending_in_range(org: Any, rng: DateRange) -> int:
    return (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.NEEDS_REVIEW, invoice_date__range=(rng.start, rng.end))
        .count()
    )


def _ledger(inv: Invoice) -> str:
    for line in inv.lines.all():
        if line.category is not None and line.category.tally_ledger_name:
            return line.category.tally_ledger_name
    return TALLY_VOUCHER[Direction(inv.direction)]


def tally_rows(invoices: Iterable[Invoice]) -> Iterator[list[str]]:
    for inv in invoices:
        yield [
            inv.invoice_date.strftime(TALLY_DATE_FORMAT),
            TALLY_VOUCHER[Direction(inv.direction)],
            inv.party.legal_name,
            _ledger(inv),
            str(inv.taxable_value),
            str(inv.cgst),
            str(inv.sgst),
            str(inv.igst),
            inv.notes,
            inv.invoice_number,
        ]


def _gst_treatment(inv: Invoice) -> str:
    if inv.supply_type == SupplyKind.EXPORT:
        return ZOHO_TREATMENT_EXPORT
    if inv.supply_type == SupplyKind.SEZ:
        return ZOHO_TREATMENT_SEZ
    if inv.party.is_composition:
        return ZOHO_TREATMENT_COMPOSITION
    return ZOHO_TREATMENT_REGISTERED if inv.party.gstin else ZOHO_TREATMENT_UNREGISTERED


def _tax_name(inv: Invoice, rate: Decimal) -> str:
    prefix = "GST" if inv.supply_type == SupplyKind.INTRA else "IGST"
    return f"{prefix}{rate_number(rate)}"


def _quantity(q: Decimal) -> str:
    return f"{q.normalize():f}"


def zoho_rows(invoices: Iterable[Invoice]) -> Iterator[list[str]]:
    for inv in invoices:
        head = [
            inv.invoice_date.isoformat(),
            inv.invoice_number,
            inv.party.legal_name,
            _gst_treatment(inv),
            inv.party.gstin or "",
            inv.place_of_supply_state_code or inv.party.state_code,
        ]
        lines = list(inv.lines.all())
        if not lines:
            yield [
                *head,
                f"Invoice {inv.invoice_number}",
                "",
                "1",
                str(inv.taxable_value),
                "",
                "",
                str(inv.total),
            ]
            continue
        for line in lines:
            yield [
                *head,
                line.description or f"Line {line.line_no}",
                line.hsn_sac,
                _quantity(line.quantity),
                str(line.unit_price),
                _tax_name(inv, line.rate),
                str(rate_number(line.rate)),
                str(line.line_total),
            ]


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


INVOICE_FIELDS = tuple(f.attname for f in Invoice._meta.concrete_fields)
LINE_FIELDS = tuple(
    f.attname for f in InvoiceLine._meta.concrete_fields if f.attname not in ("id", "invoice_id")
)
RAW_COLUMNS = (
    *INVOICE_FIELDS,
    "party_legal_name",
    "party_gstin",
    *(f"line_{name}" for name in LINE_FIELDS),
    "line_category_name",
)


def raw_rows(invoices: Iterable[Invoice]) -> Iterator[list[str]]:
    """One row per line (or one per invoice when it has no lines), header fields repeated."""
    for inv in invoices:
        head = [_cell(getattr(inv, name)) for name in INVOICE_FIELDS]
        head += [inv.party.legal_name, inv.party.gstin or ""]
        lines = list(inv.lines.all())
        if not lines:
            yield [*head, *([""] * (len(LINE_FIELDS) + 1))]
            continue
        for line in lines:
            yield [
                *head,
                *(_cell(getattr(line, name)) for name in LINE_FIELDS),
                line.category.name if line.category else "",
            ]


def render_csv(columns: tuple[str, ...], rows: Iterable[list[str]]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()


EXPORTERS: dict[str, tuple[tuple[str, ...], Callable[[Iterable[Invoice]], Iterator[list[str]]]]] = {
    "tally": (TALLY_COLUMNS, tally_rows),
    "zoho": (ZOHO_COLUMNS, zoho_rows),
    "raw": (RAW_COLUMNS, raw_rows),
}


@dataclass(frozen=True)
class CSVExport:
    filename: str
    content: str
    pending: int
    invoice_count: int


def build_csv(org: Any, kind: str, params: dict[str, str]) -> CSVExport:
    exporter = EXPORTERS.get(kind)
    if exporter is None:
        raise ExportError(f"type must be one of {', '.join(EXPORTERS)}")
    columns, rows = exporter
    rng = date_range_from_params(params)
    invoices = list(confirmed_in_range(org, rng))
    filename = f"{kind}_{rng.start.isoformat()}_{rng.end.isoformat()}.csv"
    return CSVExport(
        filename, render_csv(columns, rows(invoices)), pending_in_range(org, rng), len(invoices)
    )
