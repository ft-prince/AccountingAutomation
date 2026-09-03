"""Persistence only. PROJECT_SPECS §4: Invoice, InvoiceLine, ValidationIssue."""

from decimal import Decimal

from django.db import models

from apps.core.models import BaseModel, TenantModel

ZERO = Decimal("0")


def money(**kw):  # type: ignore[no-untyped-def]
    return models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, **kw)


class Direction(models.TextChoices):
    INWARD = "inward"  # we are the recipient (purchase)
    OUTWARD = "outward"  # we are the supplier (sale)


class SupplyKind(models.TextChoices):
    INTRA = "intra"
    INTER = "inter"
    EXPORT = "export"
    SEZ = "sez"
    IMPORT = "import"


class PaymentStatus(models.TextChoices):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    WRITTEN_OFF = "written_off"


class InvoiceStatus(models.TextChoices):
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class ValidationStatus(models.TextChoices):
    VALID = "valid"
    WARNINGS = "warnings"
    INVALID = "invalid"


class Invoice(TenantModel):
    document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    extraction_run = models.ForeignKey(
        "documents.ExtractionRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    gstin_profile = models.ForeignKey(
        "accounts.GSTINProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    party = models.ForeignKey("parties.Party", on_delete=models.PROTECT, related_name="invoices")
    direction = models.CharField(max_length=8, choices=Direction.choices)
    invoice_number = models.CharField(max_length=32)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    place_of_supply_state_code = models.CharField(max_length=2, blank=True)
    supply_type = models.CharField(
        max_length=8, choices=SupplyKind.choices, default=SupplyKind.INTRA
    )
    is_reverse_charge = models.BooleanField(default=False)
    irn = models.CharField(max_length=64, blank=True)
    has_qr = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default="INR")
    taxable_value = money()
    cgst = money()
    sgst = money()
    igst = money()
    cess = money()
    round_off = money()
    total = money()
    amount_paid = money()  # derived from PaymentAllocation (Phase 8); never set by hand
    payment_status = models.CharField(
        max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    itc_eligible = models.BooleanField(default=True)
    itc_blocked_reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=14, choices=InvoiceStatus.choices, default=InvoiceStatus.NEEDS_REVIEW
    )
    validation_status = models.CharField(
        max_length=10, choices=ValidationStatus.choices, default=ValidationStatus.VALID
    )
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=ZERO)
    layout_hash = models.CharField(max_length=64, blank=True)
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    fy = models.CharField(max_length=7)  # "2026-27"
    period_month = models.CharField(max_length=7)  # "2026-07"
    notes = models.TextField(blank=True)  # UTR / reference hints for bank matching live here
    bank_details = models.JSONField(default=dict, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["org", "party", "invoice_number", "fy"],
                condition=~models.Q(status="duplicate"),
                name="uq_invoice_number_per_fy",
            ),
            # §3.2: never both heads on one invoice.
            models.CheckConstraint(
                condition=models.Q(igst=0) | (models.Q(cgst=0) & models.Q(sgst=0)),
                name="ck_invoice_one_tax_head",
            ),
        ]
        indexes = [
            models.Index(fields=["org", "status"]),
            models.Index(fields=["org", "direction", "invoice_date"]),
            models.Index(fields=["org", "payment_status", "due_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.invoice_number} ({self.party})"


class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=500, blank=True)
    hsn_sac = models.CharField(max_length=8, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("1"))
    uom = models.CharField(max_length=20, blank=True)
    unit_price = money()
    discount = money()
    taxable_value = money()
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    cgst = money()
    sgst = money()
    igst = money()
    cess = money()
    line_total = money()
    category = models.ForeignKey(
        "parties.ExpenseCategory", null=True, blank=True, on_delete=models.SET_NULL
    )
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=ZERO)

    class Meta(BaseModel.Meta):
        ordering = ["line_no"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(igst=0) | (models.Q(cgst=0) & models.Q(sgst=0)),
                name="ck_line_one_tax_head",
            )
        ]


class ValidationIssue(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="issues")
    code = models.CharField(max_length=40)
    severity = models.CharField(max_length=10)  # error | warning
    field = models.CharField(max_length=80, blank=True)
    message = models.CharField(max_length=500)
    resolved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["created_at"]
