import inspect

import pytest
from django.urls import get_resolver
from rest_framework.viewsets import GenericViewSet

from apps.accounts.factories import GSTINProfileFactory, MembershipFactory
from apps.accounts.models import Role
from apps.core.api import OrgScopedViewSet

pytestmark = pytest.mark.django_db


def test_org_b_object_is_404_for_org_a(client_a, org_b) -> None:  # type: ignore[no-untyped-def]
    g = GSTINProfileFactory(org=org_b.org)
    assert client_a.get(f"/api/gstins/{g.id}/").status_code == 404
    assert client_a.patch(f"/api/gstins/{g.id}/", {"trade_name": "x"}).status_code == 404
    m = MembershipFactory(org=org_b.org)
    assert client_a.get(f"/api/members/{m.id}/").status_code == 404
    assert client_a.delete(f"/api/members/{m.id}/").status_code == 404


def test_list_only_shows_own_org(client_a, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    GSTINProfileFactory(org=org_a.org, gstin="27AAPFU0939F1ZV")
    GSTINProfileFactory(org=org_b.org, gstin="29AABCT1332L1ZU")
    ids = [r["gstin"] for r in client_a.get("/api/gstins/").json()["results"]]
    assert ids == ["27AAPFU0939F1ZV"]


def _registered_viewsets():  # type: ignore[no-untyped-def]
    seen = set()
    for pattern in get_resolver().url_patterns:
        for p in getattr(pattern, "url_patterns", [pattern]):
            cls = getattr(p.callback, "cls", None)
            if inspect.isclass(cls) and issubclass(cls, GenericViewSet):
                seen.add(cls)
    return sorted(seen, key=lambda c: c.__name__)


@pytest.mark.parametrize("viewset", _registered_viewsets(), ids=lambda c: c.__name__)
def test_every_viewset_is_org_scoped(viewset) -> None:  # type: ignore[no-untyped-def]
    assert issubclass(viewset, OrgScopedViewSet), f"{viewset.__name__} bypasses TenantManager"


def test_at_least_one_viewset_registered() -> None:
    assert _registered_viewsets()


def test_viewer_cannot_write(viewer_client) -> None:  # type: ignore[no-untyped-def]
    r = viewer_client.post("/api/gstins/", {"gstin": "27AAPFU0939F1ZV"}, format="json")
    assert r.status_code == 403
    r = viewer_client.patch("/api/orgs/current", {"name": "x"}, format="json")
    assert r.status_code == 403


def test_accountant_cannot_manage_members(org_a) -> None:  # type: ignore[no-untyped-def]
    from conftest import client_for

    acc = client_for(MembershipFactory(org=org_a.org, role=Role.ACCOUNTANT))
    r = acc.post("/api/members/", {"email": "n@example.com", "role": "viewer"}, format="json")
    assert r.status_code == 403


def test_owner_manages_members_and_cannot_remove_last_owner(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post("/api/members/", {"email": "n@example.com", "role": "viewer"}, format="json")
    assert r.status_code == 201
    r = client_a.delete(f"/api/members/{org_a.id}/")
    assert r.status_code == 400


def test_org_switch(org_a) -> None:  # type: ignore[no-untyped-def]
    from conftest import client_for

    second = MembershipFactory(user=org_a.user, role=Role.VIEWER)
    c = client_for(org_a)
    assert c.get("/api/auth/me").json()["org"]["id"] == str(org_a.org_id)
    assert c.post("/api/auth/me", {"org_id": str(second.org_id)}, format="json").status_code == 200
    assert c.get("/api/auth/me").json()["org"]["id"] == str(second.org_id)
