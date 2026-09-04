"""Persistence only. PROJECT_SPECS §4/§7.2: GSTR2BBatch, GSTR2BRecord, ReconciliationMatch."""

from decimal import Decimal

from django.db import models

from apps.core.models import TenantModel

ZERO = Decimal("0")


def money(**kw):  # type: ignore[no-untyped-def]
    return models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, **kw)


class BatchSource(models.TextChoices):
    JSON = "json"
    XLSX = "xlsx"


class IMSAction(models.TextChoices):
    ACCEPT = "accept"
    REJECT = "reject"
    PEND = "pend"


class MatchType(models.TextChoices):
    EXACT = "exact"
    FUZZY = "fuzzy"
    VALUE_MISMATCH = "value_mismatch"
    MISSING_IN_BOOKS = "missing_in_books"
    MISSING_IN_2B = "missing_in_2b"


class GSTR2BBatch(TenantModel):
    """One GSTR-2B download imported for one return period (§3.8: 2B is static per period)."""

    period = models.CharField(max_length=6)  # MMYYYY
    source = models.CharField(max_length=4, choices=BatchSource.choices)
    filename = models.CharField(max_length=255)
    imported_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    imported_at = models.DateTimeField()
    counts = models.JSONField(default=dict, blank=True)

    class Meta(TenantModel.Meta):
        indexes = [models.Index(fields=["org", "period"])]

    def __str__(self) -> str:
        return f"2B {self.period} ({self.filename})"


class GSTR2BRecord(TenantModel):
    batch = models.ForeignKey(GSTR2BBatch, on_delete=models.CASCADE, related_name="records")
    supplier_gstin = models.CharField(max_length=15)
    supplier_name = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=32)
    invoice_date = models.DateField()
    invoice_value = money()
    place_of_supply = models.CharField(max_length=2, blank=True)
    reverse_charge = models.BooleanField(default=False)
    taxable_value = money()
    igst = money()
    cgst = money()
    sgst = money()
    cess = money()
    itc_available = models.BooleanField(default=True)
    raw = models.JSONField(default=dict, blank=True)
    ims_action = models.CharField(max_length=6, choices=IMSAction.choices, null=True, blank=True)
    ims_note = models.CharField(max_length=500, blank=True)

    class Meta(TenantModel.Meta):
        ordering = ["invoice_date", "invoice_number"]
        indexes = [models.Index(fields=["batch", "supplier_gstin"])]

    def __str__(self) -> str:
        return f"{self.supplier_gstin} {self.invoice_number}"


class ReconciliationMatch(TenantModel):
    batch = models.ForeignKey(GSTR2BBatch, on_delete=models.CASCADE, related_name="matches")
    record = models.ForeignKey(
        GSTR2BRecord, null=True, blank=True, on_delete=models.CASCADE, related_name="matches"
    )
    invoice = models.ForeignKey(
        "invoices.Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    match_type = models.CharField(max_length=16, choices=MatchType.choices)
    delta_value = money()
    delta_tax = money()
    note = models.CharField(max_length=500, blank=True)
    resolved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "record"],
                condition=models.Q(record__isnull=False),
                name="uq_match_batch_record",
            ),
            models.UniqueConstraint(
                fields=["batch", "invoice"],
                condition=models.Q(invoice__isnull=False),
                name="uq_match_batch_invoice",
            ),
        ]
        indexes = [models.Index(fields=["batch", "match_type"])]

    def __str__(self) -> str:
        return f"{self.match_type} ({self.batch_id})"
