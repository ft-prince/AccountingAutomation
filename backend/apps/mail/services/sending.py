"""Send an approved draft. PROJECT_SPECS §6.1/§6.6: reviewer_id required, stored as
EmailMessage(outbound), edit distance (AI draft vs sent text) recorded on every reply."""

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OrgMembership
from apps.core.audit import record
from apps.mail.domain.edit_distance import levenshtein
from apps.mail.models import DraftStatus, EmailDraft, EmailMessage, MessageDirection, ThreadStatus
from apps.mail.services import send_via_provider
from apps.mail.services.review import send_refusal

REPLY_PREFIX = "Re: "


class SendRefusedError(ValueError):
    def __init__(self, kind: str, reason: str) -> None:
        super().__init__(reason)
        self.kind = kind


def _reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"{REPLY_PREFIX}{subject}"


def original_ai_text(draft: EmailDraft) -> str:
    """The body as the model produced it: the `before` of the first revision, else the body."""
    first = draft.revisions.order_by("created_at").first()
    return first.before if first else draft.body_text


def send_approved_draft(draft: EmailDraft, *, reviewer: Any) -> EmailMessage:
    membership = OrgMembership.objects.filter(org=draft.org, user=reviewer).first()
    refusal = send_refusal(draft, membership)
    if refusal is not None:
        raise SendRefusedError(*refusal)
    thread = draft.thread
    inbound = draft.in_reply_to
    to = [inbound.from_address] if inbound else []
    message = EmailMessage(
        org=draft.org,
        mailbox=thread.mailbox,
        thread=thread,
        direction=MessageDirection.OUTBOUND,
        from_address=thread.mailbox.email_address,
        to_addresses=to,
        cc_addresses=[],
        date=timezone.now(),
        subject=_reply_subject(thread.subject),
        body_text=draft.body_text,
        body_html=draft.body_html,
        is_read=True,
    )
    provider_id = send_via_provider(message, reviewer_id=reviewer.pk)
    with transaction.atomic():
        message.provider_message_id = provider_id
        message.save()
        draft.status = DraftStatus.SENT
        draft.sent_message = message
        draft.sent_at = message.date
        draft.edit_distance = levenshtein(original_ai_text(draft), draft.body_text)
        draft.save(
            update_fields=["status", "sent_message", "sent_at", "edit_distance", "updated_at"]
        )
        thread.status = ThreadStatus.REPLIED
        thread.save(update_fields=["status", "updated_at"])
        record(
            draft.org,
            actor=reviewer,
            entity=draft,
            action="draft.send",
            after={
                "reviewer_id": str(reviewer.pk),
                "draft_id": str(draft.pk),
                "sent_message_id": str(message.pk),
                "edit_distance": draft.edit_distance,
            },
        )
    return message
