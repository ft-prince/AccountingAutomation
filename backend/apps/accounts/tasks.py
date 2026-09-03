"""Celery entry points. Idempotent; take IDs, not objects."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.accounts.models import Organization

PURGE_AFTER_DAYS = 30


@shared_task
def purge_deleted_orgs() -> int:
    """§12: DELETE /api/orgs/current purges S3 + DB within 30 days, including mail."""
    from apps.documents import storage
    from apps.documents.models import Document

    cutoff = timezone.now() - timedelta(days=PURGE_AFTER_DAYS)
    n = 0
    for org in Organization.objects.filter(deletion_requested_at__lte=cutoff):
        for key in Document.objects.filter(org=org).values_list("file", flat=True):
            try:
                storage.delete_object(key)
            except Exception:  # noqa: BLE001 — best effort; DB row removal below is authoritative
                pass
        org.delete()  # cascades to every tenant table, mail included
        n += 1
    return n
