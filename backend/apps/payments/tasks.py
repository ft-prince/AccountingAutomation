"""Celery entry points. Idempotent; take IDs, not objects."""

from celery import shared_task

from apps.payments.services.allocation import refresh_overdue


@shared_task
def refresh_overdue_statuses() -> int:
    """Nightly (Beat): flip past-due invoices to overdue. PROJECT_SPECS Phase 8."""
    return refresh_overdue()
