"""Celery entry points. Idempotent; take IDs, not objects. PROJECT_SPECS §6.3, §6.6."""

import logging

from celery import shared_task
from django.conf import settings

from apps.accounts.models import User
from apps.mail.models import EmailDraft, EmailThread, MailboxConnection, MailboxStatus

log = logging.getLogger(__name__)


@shared_task
def sync_all_mailboxes() -> int:
    """Beat, every 2 minutes: fan out one sync per active mailbox (never org-wide)."""
    ids = list(
        MailboxConnection.objects.filter(status=MailboxStatus.ACTIVE)
        .exclude(encrypted_tokens="")
        .values_list("pk", flat=True)
    )
    for pk in ids:
        sync_mailbox.delay(str(pk))
    return len(ids)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def sync_mailbox(self, connection_id: str) -> str:  # type: ignore[no-untyped-def]
    from apps.mail.services.sync import sync_connection

    connection = MailboxConnection.objects.filter(pk=connection_id).first()
    if connection is None:
        return "missing"
    if connection.status == MailboxStatus.REVOKED or not connection.encrypted_tokens:
        return "skipped:revoked"
    stats = sync_connection(connection)
    return f"created={stats.created} skipped={stats.skipped}"


# Paced to the provider's tokens-per-minute budget: a burst of threads otherwise spends its
# attempts on 429s. Raise CLASSIFY_RATE_LIMIT once you are off a free tier.
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
    rate_limit=settings.CLASSIFY_RATE_LIMIT,
)
def classify_thread(self, thread_id: str) -> str:  # type: ignore[no-untyped-def]
    from apps.mail.services.classification import classify_thread as classify

    thread = EmailThread.objects.filter(pk=thread_id).first()
    if thread is None:
        return "missing"
    classify(thread)
    return f"classified:{thread.intent}"


@shared_task
def send_draft(draft_id: str, reviewer_id: str) -> str:
    """§6.6: refuses unless the draft is approved, every flag acknowledged, the reviewer holds
    the role and the mailbox can send. Refusals are recorded, never silently dropped."""
    from apps.mail.services.sending import SendRefusedError, send_approved_draft

    draft = EmailDraft.objects.filter(pk=draft_id).select_related("thread__mailbox").first()
    reviewer = User.objects.filter(pk=reviewer_id).first()
    if draft is None or reviewer is None:
        return "missing"
    try:
        message = send_approved_draft(draft, reviewer=reviewer)
    except SendRefusedError as exc:
        log.warning("send_draft refused", extra={"draft_id": draft_id, "reason": str(exc)})
        return f"refused:{exc.kind}:{exc}"
    return f"sent:{message.pk}"
