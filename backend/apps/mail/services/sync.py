"""Provider → EmailThread/EmailMessage. PROJECT_SPECS §6.3: idempotent on provider_message_id.
PDF attachments are routed to Document(source=email) with source_email_message set."""

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.documents.services import UploadError, ingest_bytes
from apps.mail.crypto import encrypt_tokens
from apps.mail.domain.injection import screen
from apps.mail.domain.sla import sla_due
from apps.mail.models import (
    EmailMessage,
    EmailThread,
    MailboxConnection,
    MailboxStatus,
    MessageDirection,
    ThreadStatus,
)
from apps.mail.providers import RawAttachment, RawMessage, provider_module
from apps.mail.sanitize import html_to_text, sanitize_html

log = logging.getLogger(__name__)

REOPEN_FROM = (ThreadStatus.REPLIED, ThreadStatus.CLOSED)


@dataclass(frozen=True)
class SyncStats:
    created: int
    skipped: int


def _is_pdf(att: RawAttachment) -> bool:
    return att.mime == "application/pdf" or att.data[:4] == b"%PDF"


def _store_attachments(message: EmailMessage, raw: list[RawAttachment]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for att in raw:
        entry: dict[str, Any] = {"filename": att.filename, "mime": att.mime, "document_id": None}
        if _is_pdf(att):
            try:
                result = ingest_bytes(
                    message.org, data=att.data, filename=att.filename, source="email"
                )
            except UploadError as exc:
                entry["error"] = str(exc)
            else:
                doc = result.document
                if doc.source_email_message_id is None:
                    doc.source_email_message = message
                    doc.save(update_fields=["source_email_message", "updated_at"])
                entry["document_id"] = str(doc.pk)
                entry["duplicate"] = result.duplicate_of is not None
        out.append(entry)
    return out


def _touch_thread(thread: EmailThread, raw: RawMessage, direction: str) -> None:
    fields = ["updated_at"]
    if not thread.subject and raw.subject:
        thread.subject = raw.subject[:500]
        fields.append("subject")
    if direction == MessageDirection.INBOUND:
        if thread.last_inbound_at is None or raw.date > thread.last_inbound_at:
            thread.last_inbound_at = raw.date
            thread.sla_due_at = sla_due(raw.date, thread.priority)
            fields += ["last_inbound_at", "sla_due_at"]
        if thread.status in REOPEN_FROM:
            thread.status = ThreadStatus.NEW
            fields.append("status")
    thread.save(update_fields=fields)


def upsert_message(connection: MailboxConnection, raw: RawMessage) -> EmailMessage | None:
    """Store one provider message; None when it already exists (idempotent)."""
    if EmailMessage.objects.filter(
        mailbox=connection, provider_message_id=raw.provider_message_id
    ).exists():
        return None
    direction = (
        MessageDirection.OUTBOUND
        if raw.from_address.lower() == connection.email_address.lower()
        else MessageDirection.INBOUND
    )
    body_text = raw.body_text or html_to_text(raw.body_html)
    note = screen(f"{raw.subject}\n{body_text}") if direction == MessageDirection.INBOUND else None
    with transaction.atomic():
        thread, _ = EmailThread.objects.get_or_create(
            mailbox=connection,
            provider_thread_id=raw.provider_thread_id,
            defaults={"org": connection.org, "subject": raw.subject[:500]},
        )
        message = EmailMessage.objects.create(
            org=connection.org,
            mailbox=connection,
            thread=thread,
            provider_message_id=raw.provider_message_id,
            rfc_message_id=raw.rfc_message_id[:998],
            direction=direction,
            from_address=raw.from_address.lower(),
            to_addresses=raw.to,
            cc_addresses=raw.cc,
            date=raw.date,
            subject=raw.subject[:500],
            body_text=body_text,
            body_html=sanitize_html(raw.body_html) if raw.body_html else "",
            is_read=raw.is_read,
            injection_flag=note is not None,
            injection_note=note or "",
        )
        if raw.attachments:
            message.attachments = _store_attachments(message, raw.attachments)
            message.save(update_fields=["attachments", "updated_at"])
        _touch_thread(thread, raw, direction)
        if direction == MessageDirection.INBOUND:
            from apps.mail.tasks import classify_thread

            thread_id = str(thread.pk)
            transaction.on_commit(lambda: classify_thread.delay(thread_id))
    return message


def sync_connection(connection: MailboxConnection) -> SyncStats:
    """Fetch new messages since the cursor and store them. Errors are recorded, then re-raised."""
    try:
        result = provider_module(connection.provider).fetch_new(connection)
        created = skipped = 0
        for raw in result.messages:
            if upsert_message(connection, raw) is None:
                skipped += 1
            else:
                created += 1
        connection.sync_cursor = result.cursor[:2000]
        connection.last_sync_at = timezone.now()
        connection.status = MailboxStatus.ACTIVE
        connection.last_error = ""
        if result.tokens is not None:
            connection.encrypted_tokens = encrypt_tokens(result.tokens)
        connection.save()
    except Exception as exc:
        connection.status = MailboxStatus.ERROR
        connection.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        connection.save(update_fields=["status", "last_error", "updated_at"])
        log.exception("mailbox sync failed", extra={"mailbox_id": str(connection.pk)})
        raise
    return SyncStats(created=created, skipped=skipped)
