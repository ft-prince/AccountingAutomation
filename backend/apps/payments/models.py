"""Persistence only. PROJECT_SPECS §4: Payment, PaymentAllocation, BankAccount, BankTransaction,
BankStatementImport, BankBalanceSnapshot."""

from decimal import Decimal

from django.db import models

from apps.core.models import BaseModel, TenantModel


def money(**kw):  # type: ignore[no-untyped-def]
    return models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"), **kw)


class PaymentDirection(models.TextChoices):
    RECEIVED = "received"
    MADE = "made"


class PaymentMethod(models.TextChoices):
    NEFT = "neft"
    UPI = "upi"
    CHEQUE = "cheque"
    CARD = "card"
    CASH = "cash"
    OTHER = "other"


class MatchStatus(models.TextChoices):
    UNMATCHED = "unmatched"
    AUTO = "auto"
    MANUAL = "manual"
    IGNORED = "ignored"


class BankAccount(TenantModel):
    name = models.CharField(max_length=100)
    bank = models.CharField(max_length=100, blank=True)
    masked_account = models.CharField(max_length=30, blank=True)
    opening_balance = money()
    opening_balance_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.masked_account})"


class BankStatementImport(BaseModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="imports")
    filename = models.CharField(max_length=255)
    format = models.CharField(max_length=10)  # csv | xlsx
    mapping = models.CharField(max_length=30)  # registry key
    rows_total = models.PositiveIntegerField(default=0)
    rows_imported = models.PositiveIntegerField(default=0)
    rows_duplicate = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )


class BankTransaction(BaseModel):
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    statement_import = models.ForeignKey(
        BankStatementImport, null=True, blank=True, on_delete=models.SET_NULL, related_name="rows"
    )
    date = models.DateField()
    amount = money()  # signed: credit > 0, debit < 0
    description = models.CharField(max_length=500, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    sha256 = models.CharField(max_length=64)
    matched_payment = models.OneToOneField(
        "payments.Payment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_txn",
    )
    match_status = models.CharField(
        max_length=10, choices=MatchStatus.choices, default=MatchStatus.UNMATCHED
    )

    class Meta(BaseModel.Meta):
        ordering = ["-date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["bank_account", "sha256"], name="uq_bank_txn_sha")
        ]
        indexes = [models.Index(fields=["bank_account", "match_status"])]


class Payment(TenantModel):
    party = models.ForeignKey(
        "parties.Party", null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    direction = models.CharField(max_length=8, choices=PaymentDirection.choices)
    amount = money()
    date = models.DateField()
    method = models.CharField(
        max_length=8, choices=PaymentMethod.choices, default=PaymentMethod.NEFT
    )
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta(TenantModel.Meta):
        indexes = [models.Index(fields=["org", "direction", "date"])]

    def __str__(self) -> str:
        return f"{self.direction} {self.amount} on {self.date}"


class PaymentAllocation(BaseModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.CASCADE, related_name="allocations"
    )
    amount = money()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "invoice"], name="uq_allocation_payment_invoice"
            ),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_allocation_positive"),
        ]


class BankBalanceSnapshot(TenantModel):
    """Manual opening-cash input for forecasting (§8.2) when no statement is imported."""

    bank_account = models.ForeignKey(
        BankAccount, null=True, blank=True, on_delete=models.CASCADE, related_name="snapshots"
    )
    date = models.DateField()
    balance = money()
    source = models.CharField(max_length=10, default="manual")  # manual | statement

    class Meta(TenantModel.Meta):
        ordering = ["-date", "-created_at"]
