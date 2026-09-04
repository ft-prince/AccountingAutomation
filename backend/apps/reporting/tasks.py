"""Celery entry points. Idempotent; take IDs, not objects."""

import logging

from celery import shared_task
from django.utils import timezone

from apps.reporting.models import ReportSchedule
from apps.reporting.schedules import deliver, is_due

log = logging.getLogger(__name__)


@shared_task
def send_due_reports() -> dict[str, int]:
    today = timezone.localdate()
    sent = failed = 0
    for schedule in ReportSchedule.objects.filter(is_active=True).select_related("org"):
        if not is_due(schedule, today):
            continue
        try:
            deliver(schedule, today)
            sent += 1
        except Exception as exc:  # noqa: BLE001 — recorded on the schedule, never swallowed
            log.exception("scheduled report failed", extra={"schedule": str(schedule.pk)})
            schedule.last_error = f"{type(exc).__name__}: {exc}"[:500]
            schedule.save(update_fields=["last_error", "updated_at"])
            failed += 1
    return {"sent": sent, "failed": failed}
