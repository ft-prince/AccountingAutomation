"""Vendor AATO inferred from e-invoice IRNs. PROJECT_SPECS §3.5."""

import pytest

from apps.core.audit import AuditEvent
from apps.invoices.factories import InvoiceFactory
from apps.parties.factories import PartyFactory
from apps.parties.tasks import infer_vendor_aato

pytestmark = pytest.mark.django_db


def _vendor_with_irn(org, irn="IRN123", status="confirmed", direction="inward", **kwargs):  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org, kind="vendor", **kwargs)
    InvoiceFactory(org=org, party=party, direction=direction, status=status, irn=irn)
    return party


def test_irn_bearing_confirmed_invoice_raises_the_bracket(org_a) -> None:  # type: ignore[no-untyped-def]
    party = _vendor_with_irn(org_a.org)
    assert infer_vendor_aato() == {"changed": 1, "skipped": 0}
    party.refresh_from_db()
    assert party.aato_bracket == "5_to_10cr" and party.aato_source == "inferred"
    assert AuditEvent.objects.filter(action="party.aato.inferred", entity_id=party.pk).count() == 1


def test_second_run_changes_nothing(org_a) -> None:  # type: ignore[no-untyped-def]
    party = _vendor_with_irn(org_a.org)
    infer_vendor_aato()
    assert infer_vendor_aato() == {"changed": 0, "skipped": 1}
    party.refresh_from_db()
    assert party.aato_bracket == "5_to_10cr"
    assert AuditEvent.objects.filter(action="party.aato.inferred").count() == 1


def test_a_bracket_a_human_set_is_never_touched(org_a) -> None:  # type: ignore[no-untyped-def]
    party = _vendor_with_irn(org_a.org, aato_bracket="above_10cr", aato_source="manual")
    assert infer_vendor_aato() == {"changed": 0, "skipped": 1}
    party.refresh_from_db()
    assert party.aato_bracket == "above_10cr" and party.aato_source == "manual"


def test_never_downgrades_an_inferred_high_bracket(org_a) -> None:  # type: ignore[no-untyped-def]
    party = _vendor_with_irn(org_a.org, aato_bracket="above_10cr", aato_source="inferred")
    infer_vendor_aato()
    party.refresh_from_db()
    assert party.aato_bracket == "above_10cr"


def test_needs_a_confirmed_inward_invoice_carrying_an_irn(org_a) -> None:  # type: ignore[no-untyped-def]
    no_irn = _vendor_with_irn(org_a.org, irn="")
    unconfirmed = _vendor_with_irn(org_a.org, status="needs_review")
    ours = _vendor_with_irn(org_a.org, direction="outward")  # our own IRN, not the party's
    untouched = PartyFactory(org=org_a.org)
    assert infer_vendor_aato() == {"changed": 0, "skipped": 0}
    for party in (no_irn, unconfirmed, ours, untouched):
        party.refresh_from_db()
        assert party.aato_bracket == "below_5cr" and party.aato_source == "manual"


def test_inference_reaches_every_org(org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    a = _vendor_with_irn(org_a.org)
    b = _vendor_with_irn(org_b.org)
    assert infer_vendor_aato()["changed"] == 2
    for party in (a, b):
        party.refresh_from_db()
        assert party.aato_source == "inferred"


@pytest.mark.django_db
def test_editing_the_bracket_takes_it_back_from_inference(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    """A human edit must stop the nightly task from overriding their judgement."""
    from apps.parties.models import Party
    from apps.parties.tasks import infer_vendor_aato

    party = PartyFactory(org=org_a.org, aato_bracket="above_10cr", aato_source="inferred")
    r = client_a.patch(f"/api/parties/{party.id}/", {"aato_bracket": "below_5cr"}, format="json")
    assert r.status_code == 200, r.json()
    party.refresh_from_db()
    assert (party.aato_bracket, party.aato_source) == ("below_5cr", "manual")
    assert r.json()["aato_source"] == "manual"
    infer_vendor_aato()
    assert Party.objects.get(pk=party.pk).aato_bracket == "below_5cr"
