"""Review and send (§6.2, §6.6, §6.7): PATCH → DraftRevision + guardrails re-run; approve refused
while any flag is unacknowledged; roles; send refused without reviewer / with pending flags;
sent mail stored as EmailMessage(outbound) with edit distance recorded; queue order; metrics."""

from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role
from apps.core.audit import AuditEvent
from apps.mail import services as gateway
from apps.mail.domain.edit_distance import levenshtein
from apps.mail.factories import DraftFactory, MailboxFactory, MessageFactory, ThreadFactory
from apps.mail.models import (
    DraftRevision,
    DraftStatus,
    EmailMessage,
    MessageDirection,
    ThreadStatus,
)
from apps.mail.providers.gmail import READ_SCOPES, SEND_SCOPE
from apps.mail.services import review
from apps.mail.tasks import send_draft
from conftest import client_for

pytestmark = pytest.mark.django_db

ORIGINAL = "Dear Sir,\n\nThank you for your email.\n\nRegards"
EDITED = "Dear Sir,\n\nThank you for your email. We have noted the update.\n\nRegards"
DISCOUNT = "Dear Sir,\n\nWe are happy to offer a 10% discount.\n\nRegards"


def make_draft(org, *, can_send: bool = True, **kw):  # type: ignore[no-untyped-def]
    scopes = [*READ_SCOPES, SEND_SCOPE] if can_send else list(READ_SCOPES)
    mailbox = MailboxFactory(org=org, scopes=scopes)
    thread = ThreadFactory(org=org, mailbox=mailbox, intent="payment_delay_notice")
    inbound = MessageFactory(thread=thread, rfc_message_id="<inbound@customer.example>")
    return DraftFactory(thread=thread, in_reply_to=inbound, body_text=ORIGINAL, **kw)


@pytest.fixture
def provider(monkeypatch):  # type: ignore[no-untyped-def]
    """Record what reaches the Gmail send call instead of hitting Google."""
    calls: list[dict] = []  # type: ignore[type-arg]

    def fake_send(tokens, **kw):  # type: ignore[no-untyped-def]
        calls.append({"tokens": tokens, **kw})
        return "sent-1"

    monkeypatch.setattr(gateway, "_provider_send_gmail", fake_send)
    return calls


# ---------------------------------------------------------------- edit / acknowledge / approve


def test_patch_records_revision_and_reruns_guardrails(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org)
    resp = client_a.patch(f"/api/mail/drafts/{draft.pk}/", {"body_text": DISCOUNT}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["guardrail_flags"] == ["promises_discount_or_waiver"]
    assert resp.json()["body_html"].startswith("<p>Dear Sir,</p>")
    revision = DraftRevision.objects.get(draft=draft)
    assert (revision.before, revision.after, revision.editor) == (ORIGINAL, DISCOUNT, org_a.user)
    # same text again is a no-op; a clean rewrite clears the flag
    client_a.patch(f"/api/mail/drafts/{draft.pk}/", {"body_text": DISCOUNT}, format="json")
    assert DraftRevision.objects.filter(draft=draft).count() == 1
    resp = client_a.patch(f"/api/mail/drafts/{draft.pk}/", {"body_text": EDITED}, format="json")
    assert resp.json()["guardrail_flags"] == []
    assert DraftRevision.objects.filter(draft=draft).count() == 2


def test_approve_is_400_until_every_flag_is_acknowledged(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(
        org_a.org, can_send=False, guardrail_flags=["party_unresolved", "legal_language"]
    )
    resp = client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    assert resp.status_code == 400
    assert "party_unresolved" in resp.json()["detail"]
    ack = f"/api/mail/drafts/{draft.pk}/acknowledge-flag/"
    assert client_a.post(ack, {"flag": "quotes_a_price"}).status_code == 400  # not raised
    assert client_a.post(ack, {"flag": "bogus"}).status_code == 400  # not a §6.5 flag
    assert client_a.post(ack, {"flag": "party_unresolved"}).status_code == 200
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/approve/").status_code == 400
    resp = client_a.post(ack, {"flag": "legal_language"})
    assert [a["flag"] for a in resp.json()["acknowledged_flags"]] == [
        "party_unresolved",
        "legal_language",
    ]
    resp = client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    assert resp.status_code == 200 and resp.json()["status"] == "approved"
    assert resp.json()["reviewed_by"] == str(org_a.user.pk)
    # §6.1: first approval on a read-only mailbox asks for the send scope; nothing is sent
    draft.thread.mailbox.refresh_from_db()
    assert draft.thread.mailbox.needs_send_scope is True
    assert AuditEvent.objects.filter(entity_id=draft.pk, action="draft.approve").exists()
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/approve/").status_code == 400  # not pending


def test_roles_viewer_cannot_touch_reviewer_can_cross_org_404(
    client_a, viewer_client, client_b, org_a
) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org)
    base = f"/api/mail/drafts/{draft.pk}/"
    assert viewer_client.get(base).status_code == 200
    assert viewer_client.patch(base, {"body_text": EDITED}, format="json").status_code == 403
    assert viewer_client.post(f"{base}approve/").status_code == 403
    assert viewer_client.post(f"{base}reject/", {"reason": "x"}).status_code == 403
    assert viewer_client.post(f"{base}send/").status_code == 403
    assert (
        viewer_client.post(f"{base}acknowledge-flag/", {"flag": "legal_language"}).status_code
        == 403
    )
    assert client_b.get(base).status_code == 404
    assert client_b.post(f"{base}approve/").status_code == 404
    assert client_a.post("/api/mail/drafts/").status_code == 405
    assert client_a.post("/api/mail/threads/").status_code == 405
    reviewer = client_for(MembershipFactory(org=org_a.org, role=Role.REVIEWER))
    resp = reviewer.post(f"{base}approve/")
    assert resp.status_code == 200 and resp.json()["status"] == "approved"


def test_edit_then_approve_is_edited_approved_and_reject_needs_reason(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org)
    client_a.patch(f"/api/mail/drafts/{draft.pk}/", {"body_text": EDITED}, format="json")
    resp = client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    assert resp.json()["status"] == "edited_approved"
    # editing after approval is refused; rejection needs a reason and reopens the thread
    assert (
        client_a.patch(
            f"/api/mail/drafts/{draft.pk}/", {"body_text": "x"}, format="json"
        ).status_code
        == 400
    )
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/reject/").status_code == 400
    assert (
        client_a.post(f"/api/mail/drafts/{draft.pk}/reject/", {"reason": "  "}).status_code == 400
    )
    resp = client_a.post(f"/api/mail/drafts/{draft.pk}/reject/", {"reason": "Too soft."})
    assert resp.status_code == 200 and resp.json()["reject_reason"] == "Too soft."
    draft.refresh_from_db()
    assert draft.status == DraftStatus.REJECTED
    assert draft.thread.status == ThreadStatus.AWAITING_REVIEW
    assert (
        client_a.post(f"/api/mail/drafts/{draft.pk}/reject/", {"reason": "again"}).status_code
        == 400
    )


# ---------------------------------------------------------------- send


def test_send_is_refused_without_reviewer_role_or_approval_or_acknowledgement(
    client_a, org_a, provider
) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org)
    viewer = MembershipFactory(org=org_a.org, role=Role.VIEWER).user
    outsider = MembershipFactory(role=Role.OWNER).user  # owner of some other org
    assert send_draft(str(draft.pk), str(viewer.pk)).startswith("refused:role:")
    assert send_draft(str(draft.pk), str(outsider.pk)).startswith("refused:role:")
    assert send_draft(str(draft.pk), str(org_a.user.pk)).startswith("refused:state:")  # pending
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/send/").status_code == 400
    client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    # a flag that appeared after approval (e.g. re-run) still blocks the send
    draft.refresh_from_db()
    draft.guardrail_flags = ["contains_bank_details"]
    draft.save()
    result = send_draft(str(draft.pk), str(org_a.user.pk))
    assert result.startswith("refused:state:") and "contains_bank_details" in result
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/send/").status_code == 400
    assert send_draft("00000000-0000-0000-0000-000000000000", str(org_a.user.pk)) == "missing"
    assert provider == []
    assert not EmailMessage.objects.filter(direction=MessageDirection.OUTBOUND).exists()
    draft.refresh_from_db()
    assert draft.status == DraftStatus.APPROVED and draft.sent_at is None


def test_send_refused_when_mailbox_lacks_send_scope(client_a, org_a, provider) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org, can_send=False)
    client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    resp = client_a.post(f"/api/mail/drafts/{draft.pk}/send/")
    assert resp.status_code == 400 and "send scope" in resp.json()["detail"]
    assert "send scope" in send_draft(str(draft.pk), str(org_a.user.pk))
    assert provider == []


def test_send_stores_outbound_message_and_edit_distance(client_a, org_a, provider) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org)
    client_a.patch(f"/api/mail/drafts/{draft.pk}/", {"body_text": EDITED}, format="json")
    client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    resp = client_a.post(f"/api/mail/drafts/{draft.pk}/send/")
    assert resp.status_code == 202, resp.content  # CELERY_TASK_ALWAYS_EAGER: already sent
    body = resp.json()
    assert body["status"] == "sent" and body["sent_at"] is not None
    assert body["edit_distance"] == levenshtein(ORIGINAL, EDITED) > 0
    assert len(provider) == 1
    call = provider[0]
    assert call["to"] == [draft.in_reply_to.from_address]
    assert call["from_address"] == draft.thread.mailbox.email_address
    assert call["subject"] == f"Re: {draft.thread.subject}"
    assert call["in_reply_to"] == "<inbound@customer.example>"
    assert call["provider_thread_id"] == draft.thread.provider_thread_id
    assert call["body_text"] == EDITED
    assert call["tokens"]["refresh_token"] == "refresh-token-secret"  # decrypted only in-process
    sent = EmailMessage.objects.get(pk=body["sent_message"])
    assert sent.direction == MessageDirection.OUTBOUND and sent.thread == draft.thread
    assert sent.provider_message_id == "sent-1" and sent.body_text == EDITED
    draft.thread.refresh_from_db()
    assert draft.thread.status == ThreadStatus.REPLIED
    event = AuditEvent.objects.get(entity_id=draft.pk, action="draft.send")
    assert event.after["reviewer_id"] == str(org_a.user.pk)
    assert event.after["draft_id"] == str(draft.pk)
    assert event.after["edit_distance"] == levenshtein(ORIGINAL, EDITED)
    # a sent draft cannot be sent, approved or edited again
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/send/").status_code == 400
    assert client_a.post(f"/api/mail/drafts/{draft.pk}/approve/").status_code == 400
    assert len(provider) == 1


def test_unedited_send_has_zero_edit_distance(org_a, provider) -> None:  # type: ignore[no-untyped-def]
    draft = make_draft(org_a.org)
    reviewer = MembershipFactory(org=org_a.org, role=Role.REVIEWER).user
    review.approve(draft, reviewer=reviewer)
    assert send_draft(str(draft.pk), str(reviewer.pk)).startswith("sent:")
    draft.refresh_from_db()
    assert draft.edit_distance == 0 and draft.status == DraftStatus.SENT


# ---------------------------------------------------------------- review queue + metrics


def test_review_queue_orders_by_sla_then_priority_and_hides_snoozed(client_a, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    mailbox = MailboxFactory(org=org)
    t0 = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)

    def pending(sla, priority, **kw):  # type: ignore[no-untyped-def]
        thread = ThreadFactory(org=org, mailbox=mailbox, sla_due_at=sla, priority=priority, **kw)
        return DraftFactory(thread=thread)

    late_normal = pending(t0, "normal")
    late_urgent = pending(t0, "urgent")
    early_low = pending(t0 - timedelta(hours=5), "low")
    snoozed = pending(
        t0 - timedelta(days=1), "urgent", snoozed_until=timezone.now() + timedelta(days=1)
    )
    approved = DraftFactory(
        thread=ThreadFactory(org=org, mailbox=mailbox), status=DraftStatus.APPROVED
    )
    DraftFactory(thread=ThreadFactory(org=org_b.org))
    body = client_a.get("/api/mail/review-queue").json()
    assert [d["id"] for d in body] == [str(early_low.pk), str(late_urgent.pk), str(late_normal.pk)]
    assert body[0]["thread"]["priority"] == "low" and "body_text" in body[0]
    assert str(snoozed.pk) not in {d["id"] for d in body}
    assert str(approved.pk) not in {d["id"] for d in body}


def test_metrics_empty_then_after_a_reply(client_a, org_a, provider) -> None:  # type: ignore[no-untyped-def]
    empty = client_a.get("/api/mail/metrics").json()
    assert empty["time_to_first_draft_seconds"] is None
    assert empty["review_time_seconds"] is None
    assert empty["mean_edit_distance"] is None
    assert empty["approval_rate_by_intent"] == {}
    assert empty["flags_per_100_drafts"] == "0.00"
    assert (
        len(empty["replies_per_day"]) == 7
        and sum(d["count"] for d in empty["replies_per_day"]) == 0
    )

    draft = make_draft(org_a.org)
    client_a.patch(f"/api/mail/drafts/{draft.pk}/", {"body_text": EDITED}, format="json")
    client_a.post(f"/api/mail/drafts/{draft.pk}/approve/")
    client_a.post(f"/api/mail/drafts/{draft.pk}/send/")
    rejected = make_draft(org_a.org, guardrail_flags=["legal_language", "quotes_a_price"])
    client_a.post(f"/api/mail/drafts/{rejected.pk}/reject/", {"reason": "no"})
    m = client_a.get("/api/mail/metrics").json()
    assert m["time_to_first_draft_seconds"] is not None and m["review_time_seconds"] is not None
    assert m["mean_edit_distance"] == f"{levenshtein(ORIGINAL, EDITED)}.00"
    assert m["approval_rate_by_intent"] == {
        "payment_delay_notice": {"approved": 1, "reviewed": 2, "rate": "0.5000"}
    }
    assert m["flags_per_100_drafts"] == "100.00"  # 2 flags over 2 drafts
    assert sum(d["count"] for d in m["replies_per_day"]) == 1
