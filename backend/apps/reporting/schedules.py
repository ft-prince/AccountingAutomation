"""Scheduled reports (§7.3): fixed, org-configured content sent through the one gateway with a
report_schedule_id. Never model text. Logged as an outbound EmailMessage with thread=null."""

from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.documents import storage
from apps.mail.models import EmailMessage, MailboxConnection, MailboxStatus, MessageDirection
from apps.mail.services import send_via_provider
from apps.reporting.domain.render import render_pdf, render_xlsx
from apps.reporting.models import Cadence, ReportSchedule
from apps.reporting.services import REPORTS, period_from_params

MIME = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def is_due(schedule: ReportSchedule, today: date) -> bool:
    if not schedule.is_active:
        return False
    if schedule.last_sent_at is None:
        return True
    last = timezone.localtime(schedule.last_sent_at).date()
    gap = {Cadence.DAILY: 1, Cadence.WEEKLY: 7, Cadence.MONTHLY: 28}[Cadence(schedule.cadence)]
    return today - last >= timedelta(days=gap)


def sending_mailbox(org: Any) -> MailboxConnection | None:
    return (
        MailboxConnection.objects.for_org(org)
        .filter(status=MailboxStatus.ACTIVE)
        .order_by("created_at")
        .first()
    )


def request_send_scope(org: Any) -> None:
    """§6.1: creating the first schedule triggers the send-scope grant if not already held."""
    mailbox = sending_mailbox(org)
    if mailbox and not mailbox.has_send_scope and not mailbox.needs_send_scope:
        mailbox.needs_send_scope = True
        mailbox.save(update_fields=["needs_send_scope", "updated_at"])


def render(schedule: ReportSchedule, today: date) -> tuple[str, bytes, dict[str, Any]]:
    fn = REPORTS[schedule.report]
    period = period_from_params({k: str(v) for k, v in schedule.params.items()}, today)
    payload = fn(schedule.org, period)
    data = (
        render_pdf(schedule.report, payload)
        if schedule.format == "pdf"
        else render_xlsx(schedule.report, payload)
    )
    return f"{schedule.report}_{period.fy}_{today.isoformat()}.{schedule.format}", data, payload


def deliver(schedule: ReportSchedule, today: date | None = None) -> EmailMessage:
    today = today or timezone.localdate()
    mailbox = sending_mailbox(schedule.org)
    if mailbox is None:
        raise RuntimeError("no active mailbox to send from")
    filename, data, payload = render(schedule, today)
    key = f"org/{schedule.org_id}/reports/{schedule.pk}/{filename}"
    storage.put_object(key, data, MIME[schedule.format])
    meta = payload.get("meta", {})
    period_meta = meta.get("period", {})
    body = "\n".join(
        [
            f"Nexren Finance scheduled report: {schedule.report}",
            f"FY {meta.get('fy')} · period {period_meta.get('from')} to {period_meta.get('to')}",
            f"Basis: {meta.get('basis')} · confirmed invoices: {meta.get('invoice_count')}"
            f" · pending: {meta.get('pending_count')}",
            "",
            f"Download (link valid 5 minutes from send): {storage.signed_get_url(key)}",
            "",
        ]
    )
    message = EmailMessage.objects.create(
        org=schedule.org,
        mailbox=mailbox,
        thread=None,
        direction=MessageDirection.OUTBOUND,
        from_address=mailbox.email_address,
        to_addresses=list(schedule.recipients),
        date=timezone.now(),
        subject=f"[{schedule.org.brand_display_name}] {schedule.report} · FY {meta.get('fy')}",
        body_text=body,
        attachments=[{"filename": filename, "mime": MIME[schedule.format], "storage_key": key}],
    )
    provider_id = send_via_provider(message, report_schedule_id=schedule.pk)
    message.provider_message_id = provider_id or ""
    message.save(update_fields=["provider_message_id", "updated_at"])
    schedule.last_sent_at = timezone.now()
    schedule.last_error = ""
    schedule.save(update_fields=["last_sent_at", "last_error", "updated_at"])
    return message
