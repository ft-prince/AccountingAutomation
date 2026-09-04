"""Celery entry points. Idempotent; take IDs, not objects."""

import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Organization
from apps.core.notifications import BackupRun, Level, notify, resolve

PURGE_AFTER_DAYS = 30

BACKUP_FAILED_CODE = "backup.failed"
BACKUP_STALE_CODE = "backup.stale"
BACKUP_DUMP_TIMEOUT_SECONDS = 60 * 60
BACKUP_CONTENT_TYPE = "application/octet-stream"


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


def _live_orgs() -> list[Organization]:
    return list(Organization.objects.filter(deletion_requested_at__isnull=True))


def _notify_every_org(*, level: str, code: str, title: str, body: str) -> None:
    for org in _live_orgs():
        notify(org, level=level, code=code, title=title, body=body, dedupe_key=code)


def _resolve_every_org(code: str) -> None:
    for org in _live_orgs():
        resolve(org, code)


def _pg_dump_bytes(target: Path) -> bytes:
    """pg_dump --format=custom into `target`. The password goes via env, never argv."""
    db = settings.DATABASES["default"]
    argv = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        f"--file={target}",
        f"--dbname={db['NAME']}",
    ]
    if db.get("HOST"):
        argv.append(f"--host={db['HOST']}")
    if db.get("PORT"):
        argv.append(f"--port={db['PORT']}")
    if db.get("USER"):
        argv.append(f"--username={db['USER']}")
    env = {"PGPASSWORD": str(db.get("PASSWORD") or "")}
    subprocess.run(  # noqa: S603 — fixed argv, no shell, values come from settings
        argv, check=True, capture_output=True, timeout=BACKUP_DUMP_TIMEOUT_SECONDS, env=env
    )
    return target.read_bytes()


@shared_task
def run_database_backup() -> str:
    """Nightly pg_dump → s3://$BACKUP_BUCKET/pg/. Failure raises an in-app alarm per org."""
    from apps.documents import storage

    started = timezone.now()
    run = BackupRun.objects.create(started_at=started)
    if not settings.BACKUP_BUCKET:
        run.error = "BACKUP_BUCKET is not configured; backup skipped"
        run.finished_at = timezone.now()
        run.save(update_fields=["error", "finished_at", "updated_at"])
        return "skipped"

    key = f"pg/nexren_{started:%Y%m%dT%H%M%SZ}.dump"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            data = _pg_dump_bytes(Path(tmp) / "nexren.dump")
        storage.put_object(key, data, BACKUP_CONTENT_TYPE, bucket=settings.BACKUP_BUCKET)
    except Exception as exc:  # noqa: BLE001 — a failed job is recorded as failed, never swallowed
        reason = getattr(exc, "stderr", None) or str(exc)
        run.error = reason.decode() if isinstance(reason, bytes) else str(reason)
        run.finished_at = timezone.now()
        run.save(update_fields=["error", "finished_at", "updated_at"])
        _notify_every_org(
            level=Level.DANGER,
            code=BACKUP_FAILED_CODE,
            title="Database backup failed",
            body=f"The nightly backup did not complete: {run.error[:500]}",
        )
        return "failed"

    run.ok = True
    run.object_key = key
    run.size_bytes = len(data)
    run.finished_at = timezone.now()
    run.save(update_fields=["ok", "object_key", "size_bytes", "finished_at", "updated_at"])
    _resolve_every_org(BACKUP_FAILED_CODE)
    _resolve_every_org(BACKUP_STALE_CODE)
    return key


@shared_task
def check_backup_freshness() -> str:
    """The reminder: warn every org when the newest good backup is older than the threshold."""
    cutoff = timezone.now() - timedelta(hours=settings.BACKUP_STALE_HOURS)
    latest = BackupRun.objects.filter(ok=True, finished_at__isnull=False).first()
    if latest is not None and latest.finished_at is not None and latest.finished_at >= cutoff:
        _resolve_every_org(BACKUP_STALE_CODE)
        return "fresh"
    seen = (
        f"last good backup {latest.finished_at:%Y-%m-%d %H:%M} UTC"
        if latest is not None and latest.finished_at is not None
        else "no successful backup has ever been recorded"
    )
    _notify_every_org(
        level=Level.WARNING,
        code=BACKUP_STALE_CODE,
        title="Database backup is stale",
        body=f"No successful backup in the last {settings.BACKUP_STALE_HOURS} hours — {seen}.",
    )
    return "stale"
