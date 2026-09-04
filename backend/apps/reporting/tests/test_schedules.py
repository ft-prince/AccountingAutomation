from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.mail.models import GMAIL_SEND_SCOPE, EmailMessage, MailboxConnection
from apps.reporting import schedules
from apps.reporting.domain.render import render_pdf, render_xlsx
from apps.reporting.models import ReportSchedule
from apps.reporting.tasks import send_due_reports

pytestmark = pytest.mark.django_db


def MailboxConnectionFactory(org, with_send_scope=False):  # type: ignore[no-untyped-def]  # noqa: N802
    return MailboxConnection.objects.create(
        org=org,
        provider="gmail",
        email_address="finance@nexren.ai",
        encrypted_tokens="",
        scopes=[GMAIL_SEND_SCOPE] if with_send_scope else [],
    )


def test_renderers_produce_files() -> None:
    payload = {
        "rows": [{"month": "2026-07", "revenue": "10.00"}],
        "meta": {"fy": "2026-27", "basis": "accrual", "pending_count": 2},
    }
    assert render_pdf("pnl", payload).startswith(b"%PDF-1.4")
    assert render_xlsx("pnl", payload)[:2] == b"PK"
    assert render_pdf("summary", {"revenue": "1", "meta": {}}).count(b"/Type /Page ") == 1


def test_create_schedule_requests_send_scope_and_owner_only(client_a, viewer_client, org_a) -> None:  # type: ignore[no-untyped-def]
    mailbox = MailboxConnectionFactory(org=org_a.org)
    body = {
        "report": "summary",
        "params": {"basis": "accrual"},
        "cadence": "monthly",
        "recipients": ["cfo@example.com"],
        "format": "pdf",
    }
    assert viewer_client.post("/api/reports/schedules/", body, format="json").status_code == 403
    r = client_a.post("/api/reports/schedules/", body, format="json")
    assert r.status_code == 201, r.json()
    mailbox.refresh_from_db()
    assert mailbox.needs_send_scope is True
    assert (
        client_a.post(
            "/api/reports/schedules/", {**body, "report": "nope"}, format="json"
        ).status_code
        == 400
    )


def test_delivery_goes_through_gateway_with_schedule_id(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mailbox = MailboxConnectionFactory(org=org_a.org, with_send_scope=True)
    sched = ReportSchedule.objects.create(
        org=org_a.org,
        report="summary",
        params={},
        cadence="daily",
        recipients=["a@b.com"],
        format="xlsx",
    )
    seen = {}

    def fake_send(message, *, reviewer_id=None, report_schedule_id=None):  # type: ignore[no-untyped-def]
        seen["schedule"] = report_schedule_id
        seen["reviewer"] = reviewer_id
        return "prov-1"

    monkeypatch.setattr(schedules, "send_via_provider", fake_send)
    monkeypatch.setattr(schedules.storage, "put_object", lambda k, d, ct: None)
    monkeypatch.setattr(schedules.storage, "signed_get_url", lambda k: "https://signed/" + k)
    assert send_due_reports() == {"sent": 1, "failed": 0}
    assert seen == {"schedule": sched.pk, "reviewer": None}
    msg = EmailMessage.objects.get(mailbox=mailbox, direction="outbound")
    assert msg.thread is None and msg.to_addresses == ["a@b.com"] and "summary" in msg.subject
    assert msg.attachments[0]["filename"].endswith(".xlsx")
    sched.refresh_from_db()
    assert sched.last_sent_at is not None
    assert send_due_reports() == {"sent": 0, "failed": 0}  # not due again today


def test_failure_is_recorded_not_swallowed(org_a) -> None:  # type: ignore[no-untyped-def]
    sched = ReportSchedule.objects.create(
        org=org_a.org, report="summary", cadence="daily", recipients=["a@b.com"]
    )
    assert send_due_reports() == {"sent": 0, "failed": 1}  # no mailbox
    sched.refresh_from_db()
    assert "no active mailbox" in sched.last_error


def test_is_due_cadence() -> None:
    s = ReportSchedule(
        cadence="weekly", is_active=True, last_sent_at=timezone.now() - timedelta(days=6)
    )
    assert schedules.is_due(s, date.today()) is False
    s.last_sent_at = timezone.now() - timedelta(days=7)
    assert schedules.is_due(s, date.today()) is True
