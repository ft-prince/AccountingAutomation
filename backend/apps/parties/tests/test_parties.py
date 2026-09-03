from io import StringIO

import pytest
from django.core.management import call_command

from apps.core.audit import AuditEvent
from apps.parties.factories import PartyFactory
from apps.parties.models import ExpenseCategory, Party
from apps.parties.services import MergeError, merge_party, party_merge_handlers

pytestmark = pytest.mark.django_db


def test_seed_categories_idempotent() -> None:
    out = StringIO()
    call_command("seed_categories", stdout=out)
    assert "16 created" in out.getvalue()
    out = StringIO()
    call_command("seed_categories", stdout=out)
    assert "0 created, 16 existing" in out.getvalue()
    assert ExpenseCategory.objects.filter(org__isnull=True).count() == 16
    meals = ExpenseCategory.objects.get(org__isnull=True, name="Meals & Entertainment")
    assert meals.itc_eligible is False and meals.section_17_5_ref == "17(5)(b)(i)"


def test_party_crud_and_search(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post(
        "/api/parties/",
        {
            "legal_name": "Acme Widgets",
            "kind": "vendor",
            "gstin": "27AAPFU0939F1ZV",
            "email_domains": ["acme.in"],
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["state_code"] == "27" and r.json()["pan"] == "AAPFU0939F"
    PartyFactory(org=org_a.org, legal_name="Zeta Corp")
    names = [p["legal_name"] for p in client_a.get("/api/parties/?q=acme").json()["results"]]
    assert names == ["Acme Widgets"]
    r = client_a.post(
        "/api/parties/", {"legal_name": "Bad", "gstin": "27AAPFU0939F1ZZ"}, format="json"
    )
    assert r.status_code == 400


def test_duplicate_gstin_per_org_rejected(client_a, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    PartyFactory(org=org_a.org, gstin="27AAPFU0939F1ZV")
    PartyFactory(org=org_b.org, gstin="27AAPFU0939F1ZV")  # fine across orgs
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        PartyFactory(org=org_a.org, gstin="27AAPFU0939F1ZV")


def test_categories_system_plus_org(client_a, org_b) -> None:  # type: ignore[no-untyped-def]
    call_command("seed_categories", stdout=StringIO())
    r = client_a.post("/api/categories/", {"name": "Drones"}, format="json")
    assert r.status_code == 201
    from apps.parties.factories import CategoryFactory

    CategoryFactory(org=org_b.org, name="Secret")
    names = {c["name"] for c in client_a.get("/api/categories/").json()["results"]}
    assert "Drones" in names and "Rent" in names and "Secret" not in names
    rent = ExpenseCategory.objects.get(org__isnull=True, name="Rent")
    assert (
        client_a.patch(f"/api/categories/{rent.id}/", {"name": "x"}, format="json").status_code
        == 400
    )
    assert client_a.delete(f"/api/categories/{rent.id}/").status_code == 400


def test_merge_sets_pointer_deactivates_and_audits(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    src = PartyFactory(org=org_a.org)
    tgt = PartyFactory(org=org_a.org)
    r = client_a.post(f"/api/parties/{src.id}/merge/", {"target": str(tgt.id)}, format="json")
    assert r.status_code == 200
    src.refresh_from_db()
    assert src.merged_into_id == tgt.id and src.is_active is False
    ev = AuditEvent.objects.get(entity_id=src.id, action="party.merge")
    assert ev.actor_id == org_a.user_id and ev.after["merged_into"] == str(tgt.id)


def test_merge_is_atomic_on_handler_failure(org_a) -> None:  # type: ignore[no-untyped-def]
    src = PartyFactory(org=org_a.org)
    tgt = PartyFactory(org=org_a.org)

    def boom(source: Party, target: Party) -> None:
        raise RuntimeError("handler exploded")

    party_merge_handlers.append(boom)
    try:
        with pytest.raises(RuntimeError):
            merge_party(src, tgt, actor=org_a.user)
    finally:
        party_merge_handlers.remove(boom)
    src.refresh_from_db()
    assert src.merged_into_id is None and src.is_active is True
    assert not AuditEvent.objects.filter(entity_id=src.id).exists()


def test_merge_guards(org_a, org_b, client_a) -> None:  # type: ignore[no-untyped-def]
    p = PartyFactory(org=org_a.org)
    with pytest.raises(MergeError):
        merge_party(p, p, actor=org_a.user)
    other = PartyFactory(org=org_b.org)
    with pytest.raises(MergeError):
        merge_party(p, other, actor=org_a.user)
    r = client_a.post(f"/api/parties/{p.id}/merge/", {"target": str(other.id)}, format="json")
    assert r.status_code == 404
