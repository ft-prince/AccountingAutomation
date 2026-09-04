"""Manual invoice entry and CSV import. Shares the recompute and validation path with the
extraction pipeline, so a typed invoice is held to exactly the same GST rules as a scanned one
(PROJECT_SPECS §3.4, §3.9). Kept out of services.py to stay a thin caller of it."""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from apps.accounts.models import GSTINProfile, Organization
from apps.core.audit import record
from apps.gst.domain.periods import fy_for_date
from apps.gst.domain.supply import SupplyType, determine_supply_type
from apps.gst.domain.tax import DEFAULT_RATE_TABLE
from apps.gst.domain.validators import InvoiceData, LineData, validate_invoice
from apps.invoices.models import Direction, Invoice, InvoiceStatus, SupplyKind, ValidationIssue
from apps.invoices.services import LineInput, _validation_status, _write_lines, recompute
from apps.parties.models import Party

CSV_COLUMNS = [
    "invoice_number",
    "invoice_date",
    "direction",
    "party_gstin",
    "party_name",
    "due_date",
    "place_of_supply",
    "is_reverse_charge",
    "irn",
    "notes",
    "description",
    "hsn_sac",
    "quantity",
    "uom",
    "unit_price",
    "discount",
    "rate",
    "cess_rate",
]


class ManualInvoiceError(ValueError):
    """User-facing failure: a bad field, an unknown party, or a duplicate number."""


def _dec(value: Any, field: str, default: str = "0") -> Decimal:
    text = str(value if value not in (None, "") else default).strip().replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ManualInvoiceError(f"{field}: {value!r} is not a number") from exc


def _date(value: Any, field: str, *, required: bool = True) -> date | None:
    if value in (None, ""):
        if required:
            raise ManualInvoiceError(f"{field} is required")
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ManualInvoiceError(f"{field}: {value!r} is not a date (use YYYY-MM-DD)")


def _flag(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class ManualLine:
    description: str
    hsn_sac: str
    quantity: Decimal
    uom: str
    unit_price: Decimal
    discount: Decimal
    rate: Decimal
    cess_rate: Decimal

    @classmethod
    def from_dict(cls, row: dict[str, Any], index: int) -> "ManualLine":
        where = f"lines[{index}]"
        return cls(
            description=str(row.get("description", "") or "")[:500],
            hsn_sac=str(row.get("hsn_sac", "") or "")[:8],
            quantity=_dec(row.get("quantity"), f"{where}.quantity", "1"),
            uom=str(row.get("uom", "") or "")[:20],
            unit_price=_dec(row.get("unit_price"), f"{where}.unit_price"),
            discount=_dec(row.get("discount"), f"{where}.discount"),
            rate=_dec(row.get("rate"), f"{where}.rate"),
            cess_rate=_dec(row.get("cess_rate"), f"{where}.cess_rate"),
        )

    def to_input(self) -> LineInput:
        return LineInput(
            description=self.description,
            hsn_sac=self.hsn_sac,
            quantity=self.quantity,
            uom=self.uom,
            unit_price=self.unit_price,
            discount=self.discount,
            rate=self.rate,
            cess_rate=self.cess_rate,
            extracted={},
        )


def _profile(org: Organization, profile_id: Any = None) -> GSTINProfile:
    qs = GSTINProfile.objects.for_org(org)
    profile = (
        qs.filter(pk=profile_id).first()
        if profile_id
        else (qs.filter(is_default=True).first() or qs.first())
    )
    if profile is None:
        raise ManualInvoiceError(
            "This organisation has no GSTIN profile. Add one in Settings first."
        )
    return profile


def _supply(profile: GSTINProfile, party: Party, direction: str, pos: str) -> SupplyType:
    supplier_state = (
        profile.state_code
        if direction == Direction.OUTWARD
        else (party.state_code or party.gstin[:2] if party.gstin else "")
    )
    return determine_supply_type(
        supplier_state or profile.state_code,
        pos or profile.state_code,
        is_export=False,
        is_sez=profile.registration_type == "sez",
    )


def _issues(
    profile: GSTINProfile,
    party: Party,
    direction: str,
    header: dict[str, Any],
    lines: list[ManualLine],
    inv_date: date,
    total: Decimal,
    pos: str,
) -> list[dict[str, Any]]:
    """Same Rule 46 and arithmetic checks the extraction path runs."""
    ours = {"name": profile.trade_name or "Us", "gstin": profile.gstin, "address": "on file"}
    theirs = {"name": party.legal_name, "gstin": party.gstin or "", "address": "on file"}
    supplier, recipient = (ours, theirs) if direction == Direction.OUTWARD else (theirs, ours)
    data = InvoiceData(
        supplier_name=supplier["name"],
        supplier_address=supplier["address"],
        supplier_gstin=supplier["gstin"],
        serial_number=str(header["invoice_number"]),
        invoice_date=inv_date,
        recipient_name=recipient["name"],
        recipient_address=recipient["address"],
        recipient_gstin=recipient["gstin"],
        place_of_supply=pos,
        is_b2b=bool(recipient["gstin"]),
        is_reverse_charge=bool(header.get("is_reverse_charge")),
        has_signature=True,  # a typed invoice is entered by a human who has the signed copy
        irn=str(header.get("irn") or "") or None,
        stated_total=total,
    )
    domain_lines = [
        LineData(
            hsn=ln.hsn_sac,
            description=ln.description,
            quantity=ln.quantity,
            unit=ln.uom,
            unit_price=ln.unit_price,
            discount=ln.discount,
            rate=ln.rate,
            cess_rate=ln.cess_rate,
            taxable_value=None,
            cgst=Decimal("0"),
            sgst=Decimal("0"),
            igst=Decimal("0"),
            cess=Decimal("0"),
        )
        for ln in lines
    ]
    einvoice = party.aato_bracket != "below_5cr" and direction == Direction.INWARD
    return [
        i.__dict__ | {"severity": str(i.severity)}
        for i in validate_invoice(
            data,
            domain_lines,
            vendor_einvoice_applicable=einvoice,
            rate_table=DEFAULT_RATE_TABLE,
            on_date=inv_date,
        )
    ]


@transaction.atomic
def create_manual_invoice(
    org: Organization, header: dict[str, Any], lines: list[dict[str, Any]], *, actor: Any
) -> Invoice:
    """Every tax figure is computed from quantity, price and rate. Nothing is trusted as typed."""
    if not lines:
        raise ManualInvoiceError("At least one line is required.")
    party = Party.objects.for_org(org).filter(pk=header.get("party")).first()
    if party is None:
        raise ManualInvoiceError("Unknown party.")
    profile = _profile(org, header.get("gstin_profile"))
    direction = header.get("direction") or Direction.INWARD
    inv_date = _date(header.get("invoice_date"), "invoice_date")
    assert inv_date is not None
    pos = str(header.get("place_of_supply_state_code") or "")[:2] or (
        party.state_code if direction == Direction.OUTWARD else profile.state_code
    )
    supply = _supply(profile, party, direction, pos)
    parsed = [ManualLine.from_dict(ln, i) for i, ln in enumerate(lines)]
    computed, totals, _ = recompute([ln.to_input() for ln in parsed], supply)
    fy = fy_for_date(inv_date)
    number = str(header.get("invoice_number") or "").strip()[:32]
    if not number:
        raise ManualInvoiceError("invoice_number is required.")
    clash = (
        Invoice.objects.for_org(org)
        .filter(party=party, invoice_number=number, fy=fy)
        .exclude(status=InvoiceStatus.DUPLICATE)
        .exists()
    )
    if clash:
        raise ManualInvoiceError(f"{number} already exists for {party.legal_name} in FY {fy}.")

    issues = _issues(
        profile,
        party,
        direction,
        {"invoice_number": number, **header},
        parsed,
        inv_date,
        totals.total,
        pos,
    )
    invoice = Invoice.objects.create(
        org=org,
        gstin_profile=profile,
        party=party,
        direction=direction,
        invoice_number=number,
        invoice_date=inv_date,
        due_date=_date(header.get("due_date"), "due_date", required=False),
        place_of_supply_state_code=pos,
        supply_type=SupplyKind(supply.value.lower()),
        is_reverse_charge=bool(header.get("is_reverse_charge")),
        irn=str(header.get("irn") or "")[:64],
        currency=str(header.get("currency") or "INR")[:3],
        taxable_value=totals.taxable,
        cgst=totals.cgst,
        sgst=totals.sgst,
        igst=totals.igst,
        cess=totals.cess,
        round_off=totals.round_off,
        total=totals.total,
        itc_eligible=direction == Direction.INWARD,
        status=InvoiceStatus.NEEDS_REVIEW,
        validation_status=_validation_status(issues),
        confidence=Decimal("1.000"),  # a human typed it; there is no model confidence to report
        fy=fy,
        period_month=inv_date.strftime("%Y-%m"),
        notes=str(header.get("notes") or ""),
        payment_terms=str(header.get("payment_terms") or "")[:100],
    )
    _write_lines(invoice, [ln.to_input() for ln in parsed], computed, party)
    ValidationIssue.objects.bulk_create(
        ValidationIssue(
            invoice=invoice,
            code=i["code"],
            severity=i["severity"],
            field=i.get("field", ""),
            message=i["message"][:500],
        )
        for i in issues
    )
    record(
        org,
        actor=actor,
        entity=invoice,
        action="invoice.manual_create",
        after={"invoice_number": number, "total": str(totals.total)},
    )
    return invoice


def _party_for_row(org: Organization, row: dict[str, Any], line_no: int) -> Party:
    gstin = str(row.get("party_gstin") or "").strip().upper()
    name = str(row.get("party_name") or "").strip()
    party = Party.objects.for_org(org).filter(gstin=gstin).first() if gstin else None
    if party is None and name:
        party = Party.objects.for_org(org).filter(legal_name__iexact=name).first()
    if party is None:
        raise ManualInvoiceError(f"row {line_no}: no party matches gstin={gstin!r} name={name!r}")
    return party


def import_csv(org: Organization, data: bytes, *, actor: Any) -> dict[str, Any]:
    """One row per invoice LINE; rows sharing an invoice_number become one invoice."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    missing = {"invoice_number", "invoice_date", "unit_price", "rate"} - {
        (f or "").strip() for f in (reader.fieldnames or [])
    }
    if missing:
        raise ManualInvoiceError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    grouped: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    for line_no, raw in enumerate(reader, start=2):
        row = {(k or "").strip(): v for k, v in raw.items()}
        number = str(row.get("invoice_number") or "").strip()
        if not number or any(e["invoice_number"] == number for e in errors):
            continue  # blank row, or a row for an invoice already rejected
        entry = grouped.setdefault(number, {"header": None, "lines": [], "row": line_no})
        if entry["header"] is None:
            try:
                party = _party_for_row(org, row, line_no)
            except ManualInvoiceError as exc:
                # One unusable row must not abort the whole file; report it per invoice.
                errors.append({"invoice_number": number, "row": line_no, "error": str(exc)})
                grouped.pop(number, None)
                continue
            entry["header"] = {
                "party": party.pk,
                "direction": (str(row.get("direction") or "inward").strip().lower() or "inward"),
                "invoice_number": number,
                "invoice_date": row.get("invoice_date"),
                "due_date": row.get("due_date"),
                "place_of_supply_state_code": str(row.get("place_of_supply") or "")[:2],
                "is_reverse_charge": _flag(row.get("is_reverse_charge")),
                "irn": row.get("irn"),
                "notes": row.get("notes"),
            }
        entry["lines"].append(row)

    created: list[dict[str, Any]] = []
    for number, entry in grouped.items():
        try:
            with transaction.atomic():
                invoice = create_manual_invoice(org, entry["header"], entry["lines"], actor=actor)
            created.append(
                {"invoice_number": number, "id": str(invoice.pk), "total": str(invoice.total)}
            )
        except (ManualInvoiceError, ValueError) as exc:
            errors.append({"invoice_number": number, "row": entry["row"], "error": str(exc)})
    return {"created": created, "errors": errors, "invoices": len(created), "failed": len(errors)}


def csv_template() -> str:
    example = {
        "invoice_number": "PUR-2026-001",
        "invoice_date": "2026-08-15",
        "direction": "inward",
        "party_gstin": "27AAPFU0939F1ZV",
        "party_name": "Acme Widgets Pvt Ltd",
        "due_date": "2026-09-14",
        "place_of_supply": "27",
        "is_reverse_charge": "no",
        "irn": "",
        "notes": "",
        "description": "Edge sensor module",
        "hsn_sac": "8543",
        "quantity": "8",
        "uom": "nos",
        "unit_price": "5000.00",
        "discount": "0",
        "rate": "18",
        "cess_rate": "0",
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerow(example)
    writer.writerow(
        {
            **example,
            "description": "Installation service",
            "hsn_sac": "998719",
            "quantity": "1",
            "unit_price": "8000.00",
        }
    )
    return buf.getvalue()
