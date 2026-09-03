"""Allocation rules and the single recompute of invoice.amount_paid / payment_status."""

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.audit import record
from apps.invoices.models import Invoice, InvoiceStatus, PaymentStatus
from apps.invoices.signals import _recomputing
from apps.parties.models import Party
from apps.parties.services import register_merge_handler
from apps.payments.models import Payment, PaymentAllocation, PaymentDirection


class AllocationError(ValueError):
    pass


@register_merge_handler
def _reassign_payments(source: Party, target: Party) -> None:
    Payment.objects.filter(party=source).update(party=target)


def derive_status(total: Decimal, paid: Decimal, due: date | None, today: date) -> str:
    """The only place payment_status is decided."""
    if paid <= 0:
        base = PaymentStatus.UNPAID
    elif paid < total:
        base = PaymentStatus.PARTIAL
    else:
        return PaymentStatus.PAID
    if due and due < today:
        return PaymentStatus.OVERDUE
    return base


def recompute_invoice(invoice: Invoice, today: date | None = None) -> Invoice:
    today = today or timezone.localdate()
    paid = PaymentAllocation.objects.filter(invoice=invoice).aggregate(s=Sum("amount"))[
        "s"
    ] or Decimal("0")
    status: str = (
        PaymentStatus.WRITTEN_OFF
        if invoice.payment_status == PaymentStatus.WRITTEN_OFF
        else derive_status(invoice.total, paid, invoice.due_date, today)
    )
    if invoice.amount_paid != paid or invoice.payment_status != status:
        invoice.amount_paid = paid
        invoice.payment_status = status
        token = _recomputing.set(True)
        try:
            invoice.save(update_fields=["amount_paid", "payment_status", "updated_at"])
        finally:
            _recomputing.reset(token)
    return invoice


def allocated_total(payment: Payment) -> Decimal:
    return payment.allocations.aggregate(s=Sum("amount"))["s"] or Decimal("0")


def allocate(
    payment: Payment, items: list[tuple[Invoice, Decimal]], *, actor: Any
) -> list[PaymentAllocation]:
    """Σ allocations ≤ payment.amount, enforced in the transaction. Replaces per-invoice rows."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        out: list[PaymentAllocation] = []
        for invoice, amount in items:
            if invoice.org_id != payment.org_id:
                raise AllocationError("Invoice belongs to another organisation.")
            if invoice.status != InvoiceStatus.CONFIRMED:
                raise AllocationError(f"Invoice {invoice.invoice_number} is not confirmed.")
            expected = "outward" if payment.direction == PaymentDirection.RECEIVED else "inward"
            if invoice.direction != expected:
                raise AllocationError(
                    f"A {payment.direction} payment cannot settle an {invoice.direction} invoice."
                )
            if amount <= 0:
                raise AllocationError("Allocation must be positive.")
            other_paid = PaymentAllocation.objects.filter(invoice=invoice).exclude(
                payment=payment
            ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other_paid + amount > invoice.total:
                raise AllocationError(
                    f"Allocation exceeds outstanding on {invoice.invoice_number}."
                )
            alloc, _ = PaymentAllocation.objects.update_or_create(
                payment=payment, invoice=invoice, defaults={"amount": amount}
            )
            out.append(alloc)
        if allocated_total(payment) > payment.amount:
            raise AllocationError("Allocations exceed the payment amount.")
        for invoice, _ in items:
            recompute_invoice(invoice)
        record(
            payment.org,
            actor=actor,
            entity=payment,
            action="payment.allocate",
            after={"allocations": [{"invoice": str(i.pk), "amount": str(a)} for i, a in items]},
        )
    return out


def refresh_overdue(org_id: Any = None) -> int:
    """Nightly: flip unpaid/partial past due_date to overdue (and back if due date moved)."""
    qs = Invoice.objects.filter(status=InvoiceStatus.CONFIRMED).exclude(
        payment_status__in=[PaymentStatus.PAID, PaymentStatus.WRITTEN_OFF]
    )
    if org_id:
        qs = qs.filter(org_id=org_id)
    n = 0
    for inv in qs.iterator():
        before = inv.payment_status
        if recompute_invoice(inv).payment_status != before:
            n += 1
    return n
