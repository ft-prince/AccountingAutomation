"""Bridge: ExtractedInvoice (Pydantic) → apps.gst.domain.validators. No tax logic lives here."""

import re
from datetime import date
from decimal import Decimal

from apps.documents.services.schema import ExtractedInvoice
from apps.gst.domain.tax import DEFAULT_RATE_TABLE
from apps.gst.domain.validators import InvoiceData, LineData, ValidationIssue, validate_invoice

_STATE_PREFIX = re.compile(r"^\s*(\d{2})")


def parse_iso_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s.strip()) if s and s.strip() else None
    except ValueError:
        return None


def state_code_of(place_of_supply: str, fallback: str) -> str:
    """'27-Maharashtra' → '27'; 'Maharashtra' → fallback (recipient state)."""
    m = _STATE_PREFIX.match(place_of_supply or "")
    return m.group(1) if m else (fallback or "")


def _cess_rate(cess: Decimal, taxable: Decimal) -> Decimal:
    """The schema captures the cess amount; the domain wants a rate. Derive, 2 dp."""
    if not cess or taxable <= 0:
        return Decimal("0")
    return (cess * 100 / taxable).quantize(Decimal("0.01"))


def to_domain(
    parsed: ExtractedInvoice, *, has_signature: bool = True
) -> tuple[InvoiceData, list[LineData]]:
    inv = parsed.invoice
    supplier, recipient = parsed.supplier, parsed.recipient
    # §3.2: place of supply defaults to the recipient state for goods.
    pos = state_code_of(inv.place_of_supply, recipient.state_code or recipient.gstin[:2])
    header = InvoiceData(
        supplier_name=supplier.name,
        supplier_address=supplier.address,
        supplier_gstin=supplier.gstin.strip().upper(),
        serial_number=inv.number.strip(),
        invoice_date=parse_iso_date(inv.date),
        recipient_name=recipient.name,
        recipient_address=recipient.address,
        recipient_gstin=recipient.gstin.strip().upper(),
        place_of_supply=pos,
        is_b2b=bool(recipient.gstin.strip()),
        is_reverse_charge=inv.is_reverse_charge,
        has_signature=has_signature,  # v1: PDF signature/DSC detection is not implemented
        irn=inv.irn.strip() or None,
        stated_total=parsed.totals.total,
    )
    lines = [
        LineData(
            hsn=ln.hsn_sac,
            description=ln.description,
            quantity=ln.quantity,
            unit=ln.uom,
            unit_price=ln.unit_price,
            discount=ln.discount,
            rate=ln.rate,
            cess_rate=_cess_rate(ln.cess, ln.taxable_value),
            taxable_value=ln.taxable_value,
            cgst=ln.cgst,
            sgst=ln.sgst,
            igst=ln.igst,
            cess=ln.cess,
        )
        for ln in parsed.lines
    ]
    return header, lines


def run_domain_validation(
    parsed: ExtractedInvoice, *, vendor_einvoice_applicable: bool = False
) -> list[ValidationIssue]:
    header, lines = to_domain(parsed)
    on_date = header.invoice_date or date.today()
    return validate_invoice(
        header,
        lines,
        vendor_einvoice_applicable=vendor_einvoice_applicable,
        rate_table=DEFAULT_RATE_TABLE,
        on_date=on_date,
    )
