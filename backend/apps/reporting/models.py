"""Persistence only. PROJECT_SPECS §7.3: ReportSchedule."""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import TenantModel


class Cadence(models.TextChoices):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportFormat(models.TextChoices):
    PDF = "pdf"
    XLSX = "xlsx"


class ReportSchedule(TenantModel):
    report = models.CharField(max_length=30)  # key in apps.reporting.services.REPORTS
    params = models.JSONField(default=dict, blank=True)  # basis, fy, from, to
    cadence = models.CharField(max_length=10, choices=Cadence.choices, default=Cadence.MONTHLY)
    recipients = ArrayField(models.EmailField(), default=list)
    format = models.CharField(max_length=4, choices=ReportFormat.choices, default=ReportFormat.PDF)
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self) -> str:
        return f"{self.report} {self.cadence} → {len(self.recipients)}"
