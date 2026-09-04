import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from apps.accounts.factories import MembershipFactory
from apps.accounts.tasks import (
    BACKUP_FAILED_CODE,
    BACKUP_STALE_CODE,
    check_backup_freshness,
    run_database_backup,
)
from apps.core.notifications import BackupRun, Level, Notification

pytestmark = pytest.mark.django_db

DUMP_BYTES = b"PGDMP-fake-dump"


class FakeBackend:
    """pg_dump and S3 are both faked: a test never shells out and never talks to the network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []
        self.buckets: list[str | None] = []
        self.fail_with: Exception | None = None

    def run(self, argv, **kwargs):  # type: ignore[no-untyped-def]
        if self.fail_with is not None:
            raise self.fail_with
        target = next(a for a in argv if a.startswith("--file=")).split("=", 1)[1]
        Path(target).write_bytes(DUMP_BYTES)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def put_object(
        self, key: str, data: bytes, content_type: str, *, bucket: str | None = None
    ) -> None:
        self.buckets.append(bucket)
        self.calls.append((key, data))


@pytest.fixture
def uploads(monkeypatch):  # type: ignore[no-untyped-def]
    backend = FakeBackend()
    monkeypatch.setattr("apps.accounts.tasks.subprocess.run", backend.run)
    monkeypatch.setattr("apps.documents.storage.put_object", backend.put_object)
    return backend


def _open_notifications(code: str):  # type: ignore[no-untyped-def]
    return Notification.objects.filter(code=code, dismissed_at__isnull=True, read_at__isnull=True)


@override_settings(BACKUP_BUCKET="nexren-backups")
def test_successful_backup_records_a_run_and_clears_alarms(uploads, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    check_backup_freshness()  # no backup has ever run: every org gets the stale warning
    assert _open_notifications(BACKUP_STALE_CODE).count() == 2

    key = run_database_backup()

    run = BackupRun.objects.get()
    assert run.ok is True
    assert uploads.buckets == [settings.BACKUP_BUCKET]  # never the document bucket
    assert run.object_key == key == uploads.calls[0][0]
    assert key.startswith("pg/nexren_") and key.endswith(".dump")
    assert run.size_bytes == len(DUMP_BYTES)
    assert run.finished_at is not None
    assert uploads.calls[0][1] == DUMP_BYTES
    assert not _open_notifications(BACKUP_STALE_CODE).exists()


@override_settings(BACKUP_BUCKET="nexren-backups")
def test_failed_pg_dump_records_reason_and_one_danger_per_org(monkeypatch, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    stderr = b"pg_dump: error: no such database"

    def boom(argv, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.CalledProcessError(1, argv, output=b"", stderr=stderr)

    monkeypatch.setattr("apps.accounts.tasks.subprocess.run", boom)

    assert run_database_backup() == "failed"

    run = BackupRun.objects.get()
    assert run.ok is False
    assert "no such database" in run.error
    assert run.finished_at is not None
    notes = _open_notifications(BACKUP_FAILED_CODE)
    assert notes.count() == 2
    assert {n.org_id for n in notes} == {org_a.org_id, org_b.org_id}
    assert all(n.level == Level.DANGER for n in notes)


@override_settings(BACKUP_BUCKET="nexren-backups")
def test_a_repeated_failure_does_not_pile_up_notifications(uploads, org_a) -> None:  # type: ignore[no-untyped-def]
    uploads.fail_with = OSError("pg_dump not installed")

    run_database_backup()
    run_database_backup()

    assert _open_notifications(BACKUP_FAILED_CODE).count() == 1
    assert BackupRun.objects.count() == 2


@override_settings(BACKUP_BUCKET="nexren-backups")
def test_a_successful_backup_resolves_the_failure_alarm(uploads, org_a) -> None:  # type: ignore[no-untyped-def]
    uploads.fail_with = OSError("disk full")
    run_database_backup()
    assert _open_notifications(BACKUP_FAILED_CODE).count() == 1

    uploads.fail_with = None
    run_database_backup()

    assert not _open_notifications(BACKUP_FAILED_CODE).exists()


@override_settings(BACKUP_BUCKET="")
def test_empty_backup_bucket_skips_with_a_recorded_reason(monkeypatch, org_a) -> None:  # type: ignore[no-untyped-def]
    def never(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("pg_dump must not run when BACKUP_BUCKET is unset")

    monkeypatch.setattr("apps.accounts.tasks.subprocess.run", never)

    assert run_database_backup() == "skipped"

    run = BackupRun.objects.get()
    assert run.ok is False
    assert "BACKUP_BUCKET" in run.error
    assert not _open_notifications(BACKUP_FAILED_CODE).exists()


@override_settings(BACKUP_STALE_HOURS=48)
def test_freshness_warns_when_the_last_good_backup_is_old(org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    old = timezone.now() - timedelta(hours=72)
    BackupRun.objects.create(started_at=old, finished_at=old, ok=True, object_key="pg/old.dump")

    assert check_backup_freshness() == "stale"

    notes = _open_notifications(BACKUP_STALE_CODE)
    assert notes.count() == 2
    assert all(n.level == Level.WARNING for n in notes)
    assert "48 hours" in notes[0].body


@override_settings(BACKUP_STALE_HOURS=48)
def test_freshness_resolves_the_warning_once_a_fresh_backup_lands(org_a) -> None:  # type: ignore[no-untyped-def]
    old = timezone.now() - timedelta(hours=72)
    BackupRun.objects.create(started_at=old, finished_at=old, ok=True)
    check_backup_freshness()
    assert _open_notifications(BACKUP_STALE_CODE).count() == 1

    now = timezone.now()
    BackupRun.objects.create(started_at=now, finished_at=now, ok=True, object_key="pg/new.dump")

    assert check_backup_freshness() == "fresh"
    assert not _open_notifications(BACKUP_STALE_CODE).exists()


@override_settings(BACKUP_STALE_HOURS=48)
def test_a_failed_run_does_not_count_as_fresh(org_a) -> None:  # type: ignore[no-untyped-def]
    now = timezone.now()
    BackupRun.objects.create(started_at=now, finished_at=now, ok=False, error="boom")

    assert check_backup_freshness() == "stale"


@override_settings(BACKUP_BUCKET="nexren-backups")
def test_orgs_pending_deletion_are_not_notified(uploads, org_a) -> None:  # type: ignore[no-untyped-def]
    doomed = MembershipFactory()
    doomed.org.deletion_requested_at = timezone.now()
    doomed.org.save(update_fields=["deletion_requested_at"])
    uploads.fail_with = OSError("nope")

    run_database_backup()

    assert [n.org_id for n in _open_notifications(BACKUP_FAILED_CODE)] == [org_a.org_id]
