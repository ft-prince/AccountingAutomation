"""Review actions on drafts. PROJECT_SPECS §6.2, §6.6: approve is refused while
guardrail_flags − acknowledged_flags ≠ ∅; roles owner/accountant/reviewer."""

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import record
from apps.mail.domain import guardrails
from apps.mail.models import (
    DraftRevision,
    DraftStatus,
    EmailDraft,
    EmailThread,
    MailboxConnection,
    ThreadStatus,
)
from apps.mail.services.drafting import snapshot_for_guardrails, text_to_html

REVIEW_ROLES = (Role.OWNER, Role.ACCOUNTANT, Role.REVIEWER)
APPROVED_STATUSES = (DraftStatus.APPROVED, DraftStatus.EDITED_APPROVED)


class ReviewError(ValueError):
    pass


class RoleError(PermissionError):
    pass


def unacknowledged_flags(draft: EmailDraft) -> list[str]:
    acked = [a.get("flag") for a in draft.acknowledged_flags if isinstance(a, dict)]
    return guardrails.unacknowledged(list(draft.guardrail_flags), [str(a) for a in acked])


def _self_reported(draft: EmailDraft) -> list[str]:
    return [f for f in draft.guardrail_flags if f == guardrails.OUTSIDE_BUSINESS_SCOPE]


def edit_draft(draft: EmailDraft, *, editor: Any, body_text: str) -> EmailDraft:
    """Record a DraftRevision and re-run the guardrails on the new text."""
    if draft.status != DraftStatus.PENDING_REVIEW:
        raise ReviewError(f"draft is {draft.status}; only pending drafts can be edited")
    if body_text == draft.body_text:
        return draft
    with transaction.atomic():
        DraftRevision.objects.create(
            draft=draft, editor=editor, before=draft.body_text, after=body_text
        )
        draft.body_text = body_text
        draft.body_html = text_to_html(body_text)
        draft.guardrail_flags = guardrails.check(
            body_text, snapshot_for_guardrails(draft.context_snapshot, _self_reported(draft))
        )
        draft.save(update_fields=["body_text", "body_html", "guardrail_flags", "updated_at"])
        record(
            draft.org,
            actor=editor,
            entity=draft,
            action="draft.edit",
            after={"flags": draft.guardrail_flags},
        )
    return draft


def acknowledge_flag(draft: EmailDraft, *, reviewer: Any, flag: str) -> EmailDraft:
    if draft.status != DraftStatus.PENDING_REVIEW:
        raise ReviewError(f"draft is {draft.status}")
    if flag not in draft.guardrail_flags:
        raise ReviewError(f"{flag} is not raised on this draft")
    entry = {"reviewer": str(reviewer.pk), "flag": flag, "at": timezone.now().isoformat()}
    draft.acknowledged_flags = [*draft.acknowledged_flags, entry]
    draft.save(update_fields=["acknowledged_flags", "updated_at"])
    record(draft.org, actor=reviewer, entity=draft, action="draft.acknowledge_flag", after=entry)
    return draft


def _mark_needs_send_scope(mailbox: MailboxConnection) -> None:
    """§6.1: send scope is requested on first draft approval unless already granted."""
    if mailbox.has_send_scope or mailbox.needs_send_scope:
        return
    mailbox.needs_send_scope = True
    mailbox.save(update_fields=["needs_send_scope", "updated_at"])


def approve(draft: EmailDraft, *, reviewer: Any) -> EmailDraft:
    if draft.status != DraftStatus.PENDING_REVIEW:
        raise ReviewError(f"draft is {draft.status}; only pending drafts can be approved")
    pending = unacknowledged_flags(draft)
    if pending:
        raise ReviewError(f"acknowledge guardrail flags before approving: {', '.join(pending)}")
    with transaction.atomic():
        edited = draft.revisions.exists()
        draft.status = DraftStatus.EDITED_APPROVED if edited else DraftStatus.APPROVED
        draft.reviewed_by = reviewer
        draft.reviewed_at = timezone.now()
        draft.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        _mark_needs_send_scope(draft.thread.mailbox)
        record(
            draft.org,
            actor=reviewer,
            entity=draft,
            action="draft.approve",
            after={"status": draft.status, "acknowledged": draft.acknowledged_flags},
        )
    return draft


def reject(draft: EmailDraft, *, reviewer: Any, reason: str) -> EmailDraft:
    if not reason.strip():
        raise ReviewError("a reason is required to reject a draft")
    if draft.status not in (DraftStatus.PENDING_REVIEW, *APPROVED_STATUSES):
        raise ReviewError(f"draft is {draft.status}")
    with transaction.atomic():
        draft.status = DraftStatus.REJECTED
        draft.reject_reason = reason
        draft.reviewed_by = reviewer
        draft.reviewed_at = timezone.now()
        draft.save(
            update_fields=["status", "reject_reason", "reviewed_by", "reviewed_at", "updated_at"]
        )
        thread: EmailThread = draft.thread
        thread.status = ThreadStatus.AWAITING_REVIEW
        thread.save(update_fields=["status", "updated_at"])
        record(
            draft.org, actor=reviewer, entity=draft, action="draft.reject", after={"reason": reason}
        )
    return draft


def send_refusal(draft: EmailDraft, reviewer_membership: Any) -> tuple[str, str] | None:
    """(kind, reason) explaining why this draft must not be sent, or None when it may.
    kind is 'role' (→ 403) or 'state' (→ 400)."""
    if reviewer_membership is None or reviewer_membership.role not in REVIEW_ROLES:
        return ("role", "reviewer must hold owner, accountant or reviewer")
    if reviewer_membership.org_id != draft.org_id:
        return ("role", "reviewer is not a member of this organisation")
    if draft.status not in APPROVED_STATUSES:
        return ("state", f"draft is {draft.status}; only approved drafts can be sent")
    pending = unacknowledged_flags(draft)
    if pending:
        return ("state", f"unacknowledged guardrail flags: {', '.join(pending)}")
    if not draft.thread.mailbox.has_send_scope:
        return ("state", "mailbox has not granted the send scope")
    return None
