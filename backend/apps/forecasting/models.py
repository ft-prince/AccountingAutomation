"""Persistence only. No logic in save(). PROJECT_SPECS §8.2, §8.4, §8.7."""

from decimal import Decimal

from django.db import models

from apps.core.models import BaseModel, TenantModel

ZERO = Decimal("0")


def money(**kw):  # type: ignore[no-untyped-def]
    return models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, **kw)


class RunStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Cadence(models.TextChoices):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ONCE = "once"


class FlowDirection(models.TextChoices):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class ForecastRun(TenantModel):
    as_of = models.DateField()
    horizon_days = models.PositiveSmallIntegerField()
    seed = models.IntegerField()
    params = models.JSONField(default=dict, blank=True)
    inputs_hash = models.CharField(max_length=64, blank=True)
    history_days = models.PositiveIntegerField(default=0)
    insufficient_history = models.BooleanField(default=False)
    opening_cash = money()
    backtest_mape = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    backtest_coverage = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    backtest_n_origins = models.PositiveSmallIntegerField(null=True, blank=True)
    runway_date = models.DateField(null=True, blank=True)
    narrative = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=RunStatus.choices, default=RunStatus.PENDING)
    error = models.TextField(blank=True)

    class Meta(TenantModel.Meta):
        indexes = [models.Index(fields=["org", "-created_at"])]

    def __str__(self) -> str:
        return f"ForecastRun {self.as_of} ({self.status})"


class ForecastPoint(BaseModel):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name="points")
    date = models.DateField()
    p10 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    p50 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    p90 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    deterministic = money()

    class Meta(BaseModel.Meta):
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["run", "date"], name="uq_forecast_point_run_date")
        ]


class Scenario(TenantModel):
    name = models.CharField(max_length=120)
    overrides = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.name


class RecurringExpensePattern(TenantModel):
    party = models.ForeignKey(
        "parties.Party", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    category = models.ForeignKey(
        "parties.ExpenseCategory", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    amount_p50 = money()
    period_days = models.PositiveSmallIntegerField()
    next_expected = models.DateField()
    confidence = models.DecimalField(max_digits=3, decimal_places=2, default=ZERO)
    occurrences = models.PositiveSmallIntegerField(default=0)
    user_confirmed = models.BooleanField(null=True, blank=True)  # None=unknown, False=dismissed
    last_detected_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        indexes = [models.Index(fields=["org", "next_expected"])]


class FixedCashflowLine(TenantModel):
    name = models.CharField(max_length=120)
    amount = money()
    cadence = models.CharField(max_length=9, choices=Cadence.choices, default=Cadence.MONTHLY)
    next_date = models.DateField()
    direction = models.CharField(
        max_length=7, choices=FlowDirection.choices, default=FlowDirection.OUTFLOW
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class ExpectedInvoice(TenantModel):
    party = models.ForeignKey("parties.Party", on_delete=models.CASCADE, related_name="+")
    amount = money()
    expected_date = models.DateField()
    probability = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("1"))
    note = models.CharField(max_length=200, blank=True)
