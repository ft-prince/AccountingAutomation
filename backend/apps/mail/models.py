"""Persistence only. No logic in save(). PROJECT_SPECS §6.2."""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import BaseModel, TenantManager, TenantModel

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GRAPH_SEND_SCOPE = "Mail.Send"


class Provider(models.TextChoices):
    GMAIL = "gmail"
    MICROSOFT = "microsoft"


class MailboxStatus(models.TextChoices):
    ACTIVE = "active"
    ERROR = "error"
    REVOKED = "revoked"


class ThreadStatus(models.TextChoices):
    NEW = "new"
    DRAFTED = "drafted"
    AWAITING_REVIEW = "awaiting_review"
    REPLIED = "replied"
    CLOSED = "closed"
    IGNORED = "ignored"


class Intent(models.TextChoices):
    """§6.4 — deterministic labels."""

    INVOICE_QUERY = "invoice_query"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    PAYMENT_DELAY_NOTICE = "payment_delay_notice"
    STATEMENT_REQUEST = "statement_request"
    QUOTE_REQUEST = "quote_request"
    PO_OR_ORDER = "po_or_order"
    DISPUTE = "dispute"
    VENDOR_BILL_RECEIVED = "vendor_bill_received"
    SUPPORT = "support"
    MEETING_OR_SCHEDULING = "meeting_or_scheduling"
    NEWSLETTER_OR_SPAM = "newsletter_or_spam"
    OTHER = "other"


class Priority(models.TextChoices):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Sentiment(models.TextChoices):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class MessageDirection(models.TextChoices):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class DraftStatus(models.TextChoices):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EDITED_APPROVED = "edited_approved"
    REJECTED = "rejected"
    SENT = "sent"
    SUPERSEDED = "superseded"


class MailboxConnection(TenantModel):
    provider = models.CharField(max_length=10, choices=Provider.choices)
    email_address = models.EmailField()
    encrypted_tokens = models.TextField(blank=True)  # Fernet token; never the raw credentials
    scopes = ArrayField(models.CharField(max_length=120), default=list, blank=True)
    status = models.CharField(
        max_length=10, choices=MailboxStatus.choices, default=MailboxStatus.ACTIVE
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    sync_cursor = models.CharField(max_length=2000, blank=True)  # historyId / deltaLink
    connected_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    needs_send_scope = models.BooleanField(default=False)  # §6.3 progressive consent

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["org", "provider", "email_address"], name="uq_mailbox_org_provider_email"
            )
        ]

    @property
    def send_scope(self) -> str:
        return GMAIL_SEND_SCOPE if self.provider == Provider.GMAIL else GRAPH_SEND_SCOPE

    @property
    def has_send_scope(self) -> bool:
        return self.send_scope in self.scopes

    def __str__(self) -> str:
        return f"{self.provider}:{self.email_address}"


class EmailThread(TenantModel):
    mailbox = models.ForeignKey(MailboxConnection, on_delete=models.CASCADE, related_name="threads")
    provider_thread_id = models.CharField(max_length=255)
    subject = models.CharField(max_length=500, blank=True)
    party = models.ForeignKey(
        "parties.Party", null=True, blank=True, on_delete=models.SET_NULL, related_name="threads"
    )
    party_resolution = models.CharField(max_length=20, blank=True)  # how the party was resolved
    linked_invoices = ArrayField(models.UUIDField(), default=list, blank=True)
    intent = models.CharField(max_length=30, choices=Intent.choices, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    sentiment = models.CharField(max_length=10, choices=Sentiment.choices, blank=True)
    requires_finance_data = models.BooleanField(default=False)
    classification_prompt_version = models.CharField(max_length=40, blank=True)
    classification_model = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=20, choices=ThreadStatus.choices, default=ThreadStatus.NEW)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["mailbox", "provider_thread_id"], name="uq_thread_mailbox_provider_id"
            )
        ]
        indexes = [
            models.Index(fields=["org", "status"]),
            models.Index(fields=["org", "intent"]),
            models.Index(fields=["org", "sla_due_at"]),
        ]

    def __str__(self) -> str:
        return self.subject or self.provider_thread_id


class EmailMessage(TenantModel):
    """§6.1: thread is nullable — report mails (§7.3) have no thread."""

    mailbox = models.ForeignKey(
        MailboxConnection, on_delete=models.CASCADE, related_name="messages"
    )
    thread = models.ForeignKey(
        EmailThread, null=True, blank=True, on_delete=models.CASCADE, related_name="messages"
    )
    provider_message_id = models.CharField(max_length=255, blank=True)
    rfc_message_id = models.CharField(max_length=998, blank=True)  # RFC 5322 Message-ID header
    direction = models.CharField(max_length=10, choices=MessageDirection.choices)
    from_address = models.EmailField()
    to_addresses = ArrayField(models.CharField(max_length=254), default=list, blank=True)
    cc_addresses = ArrayField(models.CharField(max_length=254), default=list, blank=True)
    date = models.DateTimeField()
    subject = models.CharField(max_length=500, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)  # stored sanitised (bleach); images never fetched
    attachments = models.JSONField(default=list, blank=True)  # [{filename, mime, document_id}]
    is_read = models.BooleanField(default=False)
    injection_flag = models.BooleanField(default=False)
    injection_note = models.CharField(max_length=500, blank=True)

    class Meta(TenantModel.Meta):
        ordering = ["date", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["mailbox", "provider_message_id"],
                condition=~models.Q(provider_message_id=""),
                name="uq_message_mailbox_provider_id",
            )
        ]
        indexes = [models.Index(fields=["org", "direction", "date"])]

    def __str__(self) -> str:
        return f"{self.direction} {self.subject}"


class EmailDraft(TenantModel):
    thread = models.ForeignKey(EmailThread, on_delete=models.CASCADE, related_name="drafts")
    in_reply_to = models.ForeignKey(
        EmailMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    version = models.PositiveIntegerField(default=1)
    prompt_version = models.CharField(max_length=40)
    model_name = models.CharField(max_length=60)
    context_snapshot = models.JSONField(default=dict)  # EXACTLY what the model saw
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    proposed_attachments = models.JSONField(default=list, blank=True)
    tone = models.CharField(max_length=30, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    guardrail_flags = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=DraftStatus.choices, default=DraftStatus.PENDING_REVIEW
    )
    instruction = models.TextField(blank=True)  # reviewer's regenerate instruction, if any
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )  # null = system
    reviewed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.TextField(blank=True)
    sent_message = models.ForeignKey(
        EmailMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged_flags = models.JSONField(default=list, blank=True)  # [{reviewer, flag, at}]
    edit_distance = models.PositiveIntegerField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["thread", "version"], name="uq_draft_thread_version")
        ]
        indexes = [models.Index(fields=["org", "status"])]

    def __str__(self) -> str:
        return f"draft v{self.version} ({self.status})"


class DraftRevision(BaseModel):
    draft = models.ForeignKey(EmailDraft, on_delete=models.CASCADE, related_name="revisions")
    editor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    before = models.TextField(blank=True)
    after = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["created_at"]


class StyleGuide(BaseModel):
    org = models.OneToOneField(
        "accounts.Organization", on_delete=models.CASCADE, related_name="style_guide"
    )
    sign_off = models.CharField(max_length=200, blank=True)
    tone_rules = models.TextField(blank=True)
    banned_phrases = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    must_include = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    few_shot_examples = models.JSONField(default=list, blank=True)  # max 20 (serializer)

    objects = TenantManager()

    def __str__(self) -> str:
        return f"StyleGuide({self.org_id})"


class ReplyTemplate(TenantModel):
    intent = models.CharField(max_length=30, choices=Intent.choices)
    name = models.CharField(max_length=100)
    body = models.TextField()  # {{placeholders}}

    class Meta(TenantModel.Meta):
        constraints = [models.UniqueConstraint(fields=["org", "name"], name="uq_template_org_name")]

    def __str__(self) -> str:
        return self.name
