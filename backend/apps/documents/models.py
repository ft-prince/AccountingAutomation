"""Persistence only. PROJECT_SPECS §4: Document."""

from django.db import models

from apps.core.models import AppendOnlyMixin, BaseModel, TenantModel


class DocumentSource(models.TextChoices):
    UPLOAD = "upload"
    EMAIL = "email"
    API = "api"


class DocumentStatus(models.TextChoices):
    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    NOT_INVOICE = "not_invoice"  # extracted fine, but it is a letter, report, PO, quote...


class Document(TenantModel):
    file = models.CharField(max_length=500)  # object-storage key; Django never streams it
    sha256 = models.CharField(max_length=64)
    original_filename = models.CharField(max_length=255)
    mime = models.CharField(max_length=50)
    size_bytes = models.PositiveIntegerField()
    page_count = models.PositiveSmallIntegerField(null=True, blank=True)
    source = models.CharField(
        max_length=10, choices=DocumentSource.choices, default=DocumentSource.UPLOAD
    )
    uploaded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(
        max_length=12, choices=DocumentStatus.choices, default=DocumentStatus.PENDING
    )
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    source_email_message = models.ForeignKey(
        "mail.EmailMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )

    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=["org", "sha256"], name="uq_document_sha256")]

    def __str__(self) -> str:
        return self.original_filename


class ExtractionRun(AppendOnlyMixin, BaseModel):
    """One model call. APPEND-ONLY — re-extraction creates a new run. PROJECT_SPECS §4."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="runs")
    model_name = models.CharField(max_length=60)
    prompt_version = models.CharField(max_length=40)
    raw_response = models.JSONField(null=True, blank=True)
    parsed = models.JSONField(null=True, blank=True)
    field_confidence = models.JSONField(default=dict, blank=True)
    validation_issues = models.JSONField(default=list, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_inr = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)

    @property
    def succeeded(self) -> bool:
        return self.parsed is not None and not self.error
