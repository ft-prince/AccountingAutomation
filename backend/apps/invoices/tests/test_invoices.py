import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.db import IntegrityError, transaction

from apps.accounts.factories import GSTINProfileFactory, MembershipFactory
from apps.accounts.models import Role
from apps.core.audit import AuditEvent
from apps.documents.factories import DocumentFactory
from apps.documents.models import ExtractionRun
from apps.invoices.factories import InvoiceFactory, LineFactory
from apps.invoices.models import InvoiceStatus
from apps.invoices.services import ingest_extraction
from apps.parties.factories import PartyFactory
from apps.parties.models import Party

FIXTURES = Path(settings.BASE_DIR) / "tests" / "fixtures" / "invoices"
NEXREN_GSTIN = "27AAGFF2194N1ZZ"
pytestmark = pytest.mark.django_db


def _run(org, name: str, **overrides):  # type: ignore[no-untyped-def]
    parsed = json.loads((FIXTURES / f"{name}.reply.json").read_text())
    for path, value in overrides.items():
        node = parsed
        *parents, last = path.split(".")
        for p in parents:
            node = node[int(p)] if p.isdigit() else node[p]
        node[last] = value
    doc = DocumentFactory(org=org)
    return ExtractionRun.objects.create(
        document=doc,
        model_name="m",
        prompt_version="v1",
        parsed=parsed,
        field_confidence=parsed.get("field_confidence", {}),
    )


@pytest.fixture
def nexren(org_a):  # type: ignore[no-untyped-def]
    GSTINProfileFactory(org=org_a.org, gstin=NEXREN_GSTIN, state_code="27", is_default=True)
    return org_a


def test_ingest_creates_inward_invoice_with_recomputed_tax(nexren) -> None:  # type: ignore[no-untyped-def]
    inv = ingest_extraction(_run(nexren.org, "acme_intra_18"))
    assert inv.direction == "inward" and inv.supply_type == "intra"
    assert inv.party.gstin == "27AAPFU0939F1ZV" and inv.party.kind == "vendor"
    assert (inv.taxable_value, inv.cgst, inv.sgst, inv.igst, inv.total) == (
        Decimal("33000.00"),
        Decimal("2970.00"),
        Decimal("2970.00"),
        Decimal("0"),
        Decimal("38940.00"),
    )
    assert inv.fy == "2025-26" and inv.period_month == "2025-07"
    assert inv.status == InvoiceStatus.NEEDS_REVIEW  # auto-confirm OFF by default
    assert inv.lines.count() == 2 and inv.issues.count() == 0
    assert inv.confidence == Decimal("0.960")
    assert AuditEvent.objects.filter(entity_id=inv.pk, action="invoice.ingest").exists()
    # idempotent per run
    assert ingest_extraction(inv.extraction_run).pk == inv.pk


def test_wrong_extracted_tax_figure_is_caught(nexren) -> None:  # type: ignore[no-untyped-def]
    run = _run(nexren.org, "acme_intra_18", **{"lines.0.cgst": "2200.00"})
    inv = ingest_extraction(run)
    issue = inv.issues.get(code="TAX_RECOMPUTED")
    assert issue.field == "lines[0].cgst" and "2250.00" in issue.message
    assert inv.cgst == Decimal("2970.00")  # stored figure is the recomputed one, not the extracted
    assert inv.validation_status == "warnings"


def test_inter_state_goes_to_igst_and_flags_mismatch(nexren) -> None:  # type: ignore[no-untyped-def]
    inv = ingest_extraction(_run(nexren.org, "bharat_inter_mismatch"))
    assert inv.supply_type == "inter" and inv.igst == Decimal("7200.00") and inv.cgst == 0
    assert inv.total == Decimal("47200.00")
    codes = set(inv.issues.values_list("code", flat=True))
    assert {"MISSING_FIELD", "ARITHMETIC_MISMATCH"} <= codes
    assert inv.validation_status == "invalid"


def test_duplicate_number_in_fy_is_marked_duplicate(nexren) -> None:  # type: ignore[no-untyped-def]
    first = ingest_extraction(_run(nexren.org, "acme_intra_18"))
    second = ingest_extraction(_run(nexren.org, "acme_intra_18"))
    assert second.status == InvoiceStatus.DUPLICATE and second.duplicate_of_id == first.pk
    # Same number in a different FY is a different invoice.
    third = ingest_extraction(_run(nexren.org, "acme_intra_18", **{"invoice.date": "2026-07-15"}))
    assert third.status == InvoiceStatus.NEEDS_REVIEW and third.fy == "2026-27"


def test_db_check_rejects_both_heads(org_a) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(IntegrityError), transaction.atomic():
        InvoiceFactory(
            org=org_a.org, cgst=Decimal("900"), sgst=Decimal("900"), igst=Decimal("1800")
        )
    inv = InvoiceFactory(org=org_a.org)
    with pytest.raises(IntegrityError), transaction.atomic():
        LineFactory(invoice=inv, cgst=Decimal("1"), igst=Decimal("1"))


def test_unknown_gstin_on_both_sides_is_filed_for_review_not_lost(org_a) -> None:  # type: ignore[no-untyped-def]
    """The extraction worked; refusing to store it would throw that work away. A human decides."""
    org = org_a.org
    org.name, org.legal_name, org.pan = "Someone Else", "", ""
    org.save()
    inv = ingest_extraction(_run(org, "acme_intra_18"))
    assert inv.direction == "inward" and inv.status == "needs_review"
    assert inv.validation_status == "invalid"
    issue = inv.issues.get(code="ORG_GSTIN_MISMATCH")
    assert issue.severity == "error" and "Neither GSTIN" in issue.message


def test_side_resolves_by_pan_then_by_name(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    # Recipient 27AAGFF2194N1ZZ carries PAN AAGFF2194N: another registration of ours.
    org.pan, org.name = "AAGFF2194N", "Unrelated Name"
    org.save()
    inv = ingest_extraction(_run(org, "acme_intra_18"))
    assert (
        inv.direction == "inward"
        and inv.issues.get(code="ORG_GSTIN_MISMATCH").severity == "warning"
    )
    # No PAN, but our name is printed as the recipient.
    org.pan, org.name = "", "Nexren AI Private Limited"
    org.save()
    inv2 = ingest_extraction(_run(org, "acme_intra_18", **{"invoice.number": "AW/25-26/0099"}))
    assert inv2.direction == "inward" and inv2.party.gstin == "27AAPFU0939F1ZV"
    assert inv2.issues.get(code="ORG_GSTIN_MISMATCH").severity == "error"


def test_outward_direction_when_we_are_supplier(org_a) -> None:  # type: ignore[no-untyped-def]
    GSTINProfileFactory(org=org_a.org, gstin="27AAPFU0939F1ZV")
    inv = ingest_extraction(_run(org_a.org, "acme_intra_18"))
    assert (
        inv.direction == "outward"
        and inv.party.gstin == NEXREN_GSTIN
        and inv.party.kind == "customer"
    )


def test_auto_confirm_requires_flag_and_history(nexren) -> None:  # type: ignore[no-untyped-def]
    org = nexren.org
    high = {f"k{i}": 0.99 for i in range(3)}
    org.settings = {"auto_confirm": True}
    org.save()
    inv = ingest_extraction(_run(org, "acme_intra_18", field_confidence=high))
    assert inv.status == InvoiceStatus.NEEDS_REVIEW  # < 5 confirmed with this layout
    for i in range(5):
        InvoiceFactory(
            org=org,
            party=inv.party,
            status="confirmed",
            layout_hash=inv.layout_hash,
            invoice_number=f"H{i}",
        )
    inv2 = ingest_extraction(
        _run(org, "acme_intra_18", **{"invoice.number": "AW/25-26/0043", "field_confidence": high})
    )
    assert inv2.status == InvoiceStatus.CONFIRMED
    org.settings = {}
    org.save()
    inv3 = ingest_extraction(
        _run(org, "acme_intra_18", **{"invoice.number": "AW/25-26/0044", "field_confidence": high})
    )
    assert inv3.status == InvoiceStatus.NEEDS_REVIEW


def test_patch_writes_audit_before_after_three_times(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    inv = InvoiceFactory(org=org_a.org)
    LineFactory(invoice=inv)
    for note in ["one", "two", "three"]:
        r = client_a.patch(f"/api/invoices/{inv.id}/", {"notes": note}, format="json")
        assert r.status_code == 200, r.json()
    events = list(
        AuditEvent.objects.filter(entity_id=inv.pk, action="invoice.edit").order_by("created_at")
    )
    assert [e.after["notes"] for e in events] == ["one", "two", "three"]
    assert [e.before["notes"] for e in events] == ["", "one", "two"]


def test_patch_lines_recomputes_totals_server_side(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    inv = InvoiceFactory(org=org_a.org)
    lines = [
        {
            "description": "A",
            "hsn_sac": "8543",
            "quantity": "2",
            "unit_price": "617.28",
            "rate": "5",
        },
        {
            "description": "B",
            "hsn_sac": "9987",
            "quantity": "1",
            "unit_price": "1000",
            "rate": "18",
        },
    ]
    r = client_a.patch(f"/api/invoices/{inv.id}/", {"lines": lines}, format="json")
    body = r.json()
    assert r.status_code == 200, body
    assert body["taxable_value"] == "2234.56"
    assert body["cgst"] == "120.86" and body["sgst"] == "120.86"  # 30.86 + 90.00
    assert body["total"] == "2476.00" and body["round_off"] == "-0.28"
    assert body["lines"][0]["cgst"] == "30.86"


def test_derived_fields_cannot_be_patched(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    inv = InvoiceFactory(org=org_a.org)
    r = client_a.patch(f"/api/invoices/{inv.id}/", {"amount_paid": "100"}, format="json")
    assert r.status_code == 400


def test_confirm_role_and_error_gate(client_a, viewer_client, org_a) -> None:  # type: ignore[no-untyped-def]
    inv = InvoiceFactory(org=org_a.org)
    inv.issues.create(code="MISSING_FIELD", severity="error", field="irn", message="x")
    assert viewer_client.post(f"/api/invoices/{inv.id}/confirm/").status_code == 403
    reviewer = MembershipFactory(org=org_a.org, role=Role.REVIEWER)
    from conftest import client_for

    assert client_for(reviewer).post(f"/api/invoices/{inv.id}/confirm/").status_code == 403
    r = client_a.post(f"/api/invoices/{inv.id}/confirm/", {}, format="json")
    assert r.status_code == 400 and r.json()["errors"]["issues"][0]["code"] == "MISSING_FIELD"
    r = client_a.post(f"/api/invoices/{inv.id}/confirm/", {"force": True}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert AuditEvent.objects.filter(entity_id=inv.pk, action="invoice.confirmed").exists()


def test_reject_needs_reason_and_reviewer_may(org_a) -> None:  # type: ignore[no-untyped-def]
    from conftest import client_for

    inv = InvoiceFactory(org=org_a.org)
    c = client_for(MembershipFactory(org=org_a.org, role=Role.REVIEWER))
    assert c.post(f"/api/invoices/{inv.id}/reject/", {}, format="json").status_code == 400
    r = c.post(f"/api/invoices/{inv.id}/reject/", {"reason": "not ours"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_mark_duplicate_and_bulk_confirm(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    a = InvoiceFactory(org=org_a.org)
    b = InvoiceFactory(org=org_a.org, party=a.party)
    c = InvoiceFactory(org=org_a.org)
    r = client_a.post(
        f"/api/invoices/{b.id}/mark-duplicate/", {"duplicate_of": str(a.id)}, format="json"
    )
    assert r.status_code == 200 and r.json()["duplicate_of"] == str(a.id)
    r = client_a.post(
        "/api/invoices/bulk-confirm/", {"ids": [str(a.id), str(b.id), str(c.id)]}, format="json"
    )
    assert r.json()["results"] == {str(a.id): "confirmed", str(c.id): "confirmed"}


def test_filters_and_review_queue(client_a, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    low = InvoiceFactory(
        org=org_a.org, confidence=Decimal("0.5"), direction="outward", total=Decimal("500")
    )
    InvoiceFactory(org=org_a.org, confidence=Decimal("0.99"), status="confirmed")
    InvoiceFactory(org=org_b.org)
    q = client_a.get("/api/invoices/review-queue/").json()["results"]
    assert [x["id"] for x in q] == [str(low.id)] + [x["id"] for x in q[1:]]
    assert len(client_a.get("/api/invoices/").json()["results"]) == 2
    assert len(client_a.get("/api/invoices/?direction=outward").json()["results"]) == 1
    assert len(client_a.get("/api/invoices/?status=confirmed").json()["results"]) == 1
    assert len(client_a.get("/api/invoices/?max=600").json()["results"]) == 1
    assert len(client_a.get(f"/api/invoices/?party={low.party_id}").json()["results"]) == 1
    assert (
        len(
            client_a.get(
                "/api/invoices/?fy=2026-27&period=2026-07&from=2026-07-01&to=2026-07-31"
            ).json()["results"]
        )
        == 2
    )


def test_party_merge_moves_invoices(org_a) -> None:  # type: ignore[no-untyped-def]
    from apps.parties.services import merge_party

    a, b = PartyFactory(org=org_a.org), PartyFactory(org=org_a.org)
    inv = InvoiceFactory(org=org_a.org, party=a)
    merge_party(a, b, actor=org_a.user)
    inv.refresh_from_db()
    assert inv.party_id == b.pk and Party.objects.get(pk=a.pk).merged_into_id == b.pk
