"""Builders for confirmed invoices and allocated payments used by the DB-level tests."""

from datetime import date, timedelta
from decimal import Decimal

from apps.invoices.factories import InvoiceFactory
from apps.invoices.models import Invoice
from apps.payments.factories import PaymentFactory
from apps.payments.models import PaymentAllocation

_counter = {"n": 0}


def confirmed_invoice(
    org,
    party,
    *,
    direction: str,
    invoice_date: date,
    taxable: str,
    due_date: date | None | str = "default",
    **kw,
) -> Invoice:  # type: ignore[no-untyped-def]
    """Intra-state 18% invoice: total = taxable * 1.18. `due_date="default"` means +30 days."""
    _counter["n"] += 1
    tv = Decimal(taxable)
    half = (tv * Decimal("0.09")).quantize(Decimal("0.01"))
    if due_date == "default":
        due_date = invoice_date + timedelta(days=30)
    status = kw.pop("status", "confirmed")
    return InvoiceFactory(
        org=org,
        party=party,
        direction=direction,
        invoice_number=f"{direction[:3].upper()}-{_counter['n']:05d}",
        invoice_date=invoice_date,
        due_date=due_date,
        taxable_value=tv,
        cgst=half,
        sgst=half,
        total=tv + half + half,
        fy=_fy(invoice_date),
        period_month=invoice_date.strftime("%Y-%m"),
        status=status,
        **kw,
    )


def _fy(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def pay(invoice: Invoice, on: date, amount: Decimal | None = None) -> PaymentAllocation:
    amount = amount if amount is not None else invoice.total
    payment = PaymentFactory(
        org=invoice.org,
        party=invoice.party,
        direction="received" if invoice.direction == "outward" else "made",
        amount=amount,
        date=on,
    )
    return PaymentAllocation.objects.create(payment=payment, invoice=invoice, amount=amount)
