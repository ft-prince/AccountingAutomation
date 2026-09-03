from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.api_keys import verify
from apps.accounts.models import Organization
from apps.accounts.tasks import purge_deleted_orgs
from apps.core.audit import AuditEvent

pytestmark = pytest.mark.django_db


def test_settings_default_off_and_owner_only(client_a, viewer_client) -> None:  # type: ignore[no-untyped-def]
    assert client_a.get("/api/settings").json()["auto_confirm"] is False
    assert (
        viewer_client.put("/api/settings", {"auto_confirm": True}, format="json").status_code == 403
    )
    r = client_a.put("/api/settings", {"auto_confirm": True}, format="json")
    assert r.status_code == 200 and r.json()["auto_confirm"] is True
    assert AuditEvent.objects.filter(action="org.settings").exists()


def test_api_keys_shown_once_and_revocable(client_a, viewer_client) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post("/api/api-keys/", {"name": "erp"}, format="json")
    assert r.status_code == 201
    raw = r.json()["key"]
    assert (
        raw.startswith("nxf_") and "key" not in client_a.get("/api/api-keys/").json()["results"][0]
    )
    assert verify(raw) is not None
    assert viewer_client.post("/api/api-keys/", {"name": "x"}, format="json").status_code == 403
    assert client_a.delete(f"/api/api-keys/{r.json()['id']}/").status_code == 204
    assert verify(raw) is None


def test_org_deletion_is_owner_only_and_purged_after_30_days(
    client_a, viewer_client, org_a, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    assert viewer_client.delete("/api/orgs/current").status_code == 403
    r = client_a.delete("/api/orgs/current")
    assert r.status_code == 202
    assert purge_deleted_orgs() == 0  # not yet 30 days
    org = Organization.objects.get(pk=org_a.org_id)
    org.deletion_requested_at = timezone.now() - timedelta(days=31)
    org.save()
    from apps.documents import storage

    monkeypatch.setattr(storage, "delete_object", lambda key: None)
    assert purge_deleted_orgs() == 1
    assert not Organization.objects.filter(pk=org_a.org_id).exists()
