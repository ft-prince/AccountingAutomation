"""Guard: invoice.amount_paid and payment_status are DERIVED (PROJECT_SPECS §4, Phase 8).
Only apps.payments.services.allocation.recompute_invoice may change them."""

import contextvars

from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.invoices.models import Invoice

_recomputing: contextvars.ContextVar[bool] = contextvars.ContextVar("recomputing", default=False)


class DerivedFieldError(ValueError):
    pass


@receiver(pre_save, sender=Invoice)
def _guard_derived_fields(sender, instance: Invoice, **kwargs) -> None:  # type: ignore[no-untyped-def]
    if instance._state.adding or _recomputing.get():
        return
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and not ({"amount_paid", "payment_status"} & set(update_fields)):
        return
    current = Invoice.objects.filter(pk=instance.pk).values("amount_paid", "payment_status").first()
    if current and (
        current["amount_paid"] != instance.amount_paid
        or current["payment_status"] != instance.payment_status
    ):
        raise DerivedFieldError("amount_paid / payment_status are derived from allocations.")
