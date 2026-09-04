import pytest

from apps.core.notifications import Level, Notification, notify, resolve

pytestmark = pytest.mark.django_db


def _notify(org, **kw):  # type: ignore[no-untyped-def]
    defaults = {"level": Level.WARNING, "code": "backup.stale", "title": "stale", "body": "b"}
    return notify(org, **{**defaults, **kw})


def test_dedupe_key_refreshes_the_open_notification_instead_of_piling_up(org_a) -> None:  # type: ignore[no-untyped-def]
    first = _notify(org_a.org, dedupe_key="backup.stale")
    second = _notify(org_a.org, dedupe_key="backup.stale", body="newer")

    assert first.pk == second.pk
    assert Notification.objects.for_org(org_a.org).count() == 1
    assert second.body == "newer"


def test_a_read_notification_no_longer_blocks_a_new_one(org_a) -> None:  # type: ignore[no-untyped-def]
    first = _notify(org_a.org, dedupe_key="backup.stale")
    Notification.objects.filter(pk=first.pk).update(read_at="2026-01-01T00:00:00Z")

    second = _notify(org_a.org, dedupe_key="backup.stale")

    assert second.pk != first.pk
    assert Notification.objects.for_org(org_a.org).count() == 2


def test_dedupe_is_per_org(org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    a = _notify(org_a.org, dedupe_key="backup.stale")
    b = _notify(org_b.org, dedupe_key="backup.stale")

    assert a.pk != b.pk


def test_resolve_dismisses_the_open_notification_and_is_idempotent(org_a) -> None:  # type: ignore[no-untyped-def]
    note = _notify(org_a.org, dedupe_key="backup.stale")

    assert resolve(org_a.org, "backup.stale") == 1
    assert resolve(org_a.org, "backup.stale") == 0
    note.refresh_from_db()
    assert note.dismissed_at is not None
    assert note.is_open is False


def test_entity_is_stored_for_deep_links(org_a) -> None:  # type: ignore[no-untyped-def]
    note = _notify(org_a.org, entity=org_a.org)

    assert note.entity_type == "Organization"
    assert note.entity_id == org_a.org.pk


def test_list_hides_dismissed_and_unread_filter_works(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    open_note = _notify(org_a.org, dedupe_key="backup.stale")
    read_note = _notify(org_a.org, code="mailbox.disconnected", dedupe_key="mailbox.disconnected")
    client_a.post(f"/api/notifications/{read_note.id}/read/")
    dismissed = _notify(org_a.org, code="x", dedupe_key="x")
    client_a.post(f"/api/notifications/{dismissed.id}/dismiss/")

    all_ids = [r["id"] for r in client_a.get("/api/notifications/").json()["results"]]
    unread_ids = [r["id"] for r in client_a.get("/api/notifications/?unread=1").json()["results"]]

    assert str(dismissed.id) not in all_ids
    assert {str(open_note.id), str(read_note.id)} == set(all_ids)
    assert unread_ids == [str(open_note.id)]


def test_read_all_marks_every_unread_notification(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    _notify(org_a.org, dedupe_key="a")
    _notify(org_a.org, code="b", dedupe_key="b")

    r = client_a.post("/api/notifications/read-all/")

    assert r.status_code == 200
    assert r.json() == {"marked_read": 2}
    assert not Notification.objects.for_org(org_a.org).filter(read_at__isnull=True).exists()


def test_org_b_notification_is_404_for_org_a(client_a, org_b) -> None:  # type: ignore[no-untyped-def]
    other = _notify(org_b.org, dedupe_key="backup.stale")

    assert client_a.get(f"/api/notifications/{other.id}/").status_code == 404
    assert client_a.post(f"/api/notifications/{other.id}/read/").status_code == 404
    assert client_a.get("/api/notifications/").json()["results"] == []


def test_viewer_can_read_and_dismiss_own_org_notifications(viewer_client, org_a) -> None:  # type: ignore[no-untyped-def]
    note = _notify(org_a.org, dedupe_key="backup.stale")

    assert viewer_client.post(f"/api/notifications/{note.id}/read/").status_code == 200
    assert viewer_client.post(f"/api/notifications/{note.id}/dismiss/").status_code == 200
    note.refresh_from_db()
    assert note.dismissed_at is not None


def test_notifications_cannot_be_created_over_the_api(client_a) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post("/api/notifications/", {"code": "x", "title": "y"}, format="json")

    assert r.status_code == 400
