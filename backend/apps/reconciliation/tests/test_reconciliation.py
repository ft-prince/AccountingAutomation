"""Service + API coverage for GSTR-2B import, matching, overrides and IMS (§3.8, §7.2, §10).

The seeded fixture classifies into every match type with exact counts:
  3 exact · 2 fuzzy · 1 value_mismatch · 2 missing_in_books · 2 missing_in_2b
and an ITC-at-risk total of ₹1,450 (₹100 disputed tax + ₹900 + ₹450 unclaimed 2B tax).
"""

import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role
from apps.core.audit import AuditEvent
from apps.invoices.factories import InvoiceFactory
from apps.parties.factories import PartyFactory
from apps.reconciliation import services
from apps.reconciliation.models import GSTR2BBatch, GSTR2BRecord, ReconciliationMatch
from conftest import client_for

pytestmark = pytest.mark.django_db
D = Decimal
PERIOD = "072026"
S1 = "27AABCT1332L1ZU"
S2 = "29AAACR5055K1Z7"
EXPECTED_COUNTS = {
    "exact": 3,
    "fuzzy": 2,
    "value_mismatch": 1,
    "missing_in_books": 2,
    "missing_in_2b": 2,
}
EXPECTED_AT_RISK = D("1450.00")

# (gstin, inum, idt, val, txval, cgst, sgst, itcavl)
RECORDS_2B: tuple[tuple[str, str, str, int, int, int, int, str], ...] = (
    (S1, "INV-001", "05-07-2026", 11800, 10000, 900, 900, "Y"),  # exact
    (S1, "INV-002", "06-07-2026", 5900, 5000, 450, 450, "Y"),  # exact
    (S2, "INV-003", "07-07-2026", 23600, 20000, 1800, 1800, "Y"),  # exact
    (S1, "INV/004", "08-07-2026", 8260, 7000, 630, 630, "Y"),  # fuzzy: "/" vs "-"
    (S1, "INV-005", "10-07-2026", 11800, 10000, 900, 900, "Y"),  # fuzzy: books dated +2d
    (S1, "INV-006", "11-07-2026", 17700, 15000, 1350, 1350, "Y"),  # value_mismatch (Δ500/Δ100)
    (S1, "INV-007", "20-07-2026", 5900, 5000, 450, 450, "Y"),  # missing_in_books (tax 900)
    (S2, "INV-008", "21-07-2026", 2950, 2500, 225, 225, "N"),  # missing_in_books (tax 450)
)
# (gstin, number, date, taxable, cgst, sgst, total)
BOOKS: tuple[tuple[str, str, date, int, int, int, int], ...] = (
    (S1, "INV-001", date(2026, 7, 5), 10000, 900, 900, 11800),
    (S1, "INV-002", date(2026, 7, 6), 5000, 450, 450, 5900),
    (S2, "INV-003", date(2026, 7, 7), 20000, 1800, 1800, 23600),
    (S1, "INV-004", date(2026, 7, 8), 7000, 630, 630, 8260),
    (S1, "INV-005", date(2026, 7, 12), 10000, 900, 900, 11800),
    (S1, "INV-006", date(2026, 7, 11), 14600, 1300, 1300, 17200),
    (S1, "INV-009", date(2026, 7, 2), 6000, 540, 540, 7080),  # missing_in_2b
    (S2, "INV-010", date(2026, 7, 28), 4000, 360, 360, 4720),  # missing_in_2b
)
EXCEL_HEADER = [
    "GSTIN of supplier",
    "Trade/Legal name of the Supplier",
    "Invoice number",
    "Invoice type",
    "Invoice Date",
    "Invoice Value(₹)",
    "Place of supply",
    "Supply Attract Reverse Charge",
    "Rate(%)",
    "Taxable Value (₹)",
    "Integrated Tax(₹)",
    "Central Tax(₹)",
    "State/UT Tax(₹)",
    "Cess(₹)",
    "ITC Availability",
]


def json_2b(records: tuple[tuple[Any, ...], ...] = RECORDS_2B, period: str = PERIOD) -> bytes:
    suppliers: dict[str, list[dict[str, Any]]] = {}
    for gstin, inum, idt, val, txval, cgst, sgst, itcavl in records:
        suppliers.setdefault(gstin, []).append(
            {
                "inum": inum,
                "idt": idt,
                "val": val,
                "pos": gstin[:2],
                "rev": "N",
                "itcavl": itcavl,
                "txval": txval,
                "igst": 0,
                "cgst": cgst,
                "sgst": sgst,
                "cess": 0,
            }
        )
    payload = {
        "data": {
            "gstin": "27AAPFU0939F1ZV",
            "rtnprd": period,
            "docdata": {
                "b2b": [
                    {"ctin": gstin, "trdnm": f"Supplier {gstin[:2]}", "inv": inv}
                    for gstin, inv in suppliers.items()
                ]
            },
        }
    }
    return json.dumps(payload).encode()


def excel_2b(records: tuple[tuple[Any, ...], ...] = RECORDS_2B) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "B2B"
    sheet.append(["Goods and Services Tax - GSTR-2B"])
    sheet.append(["Taxable inward supplies received from registered persons"])
    sheet.append([])
    sheet.append(EXCEL_HEADER)
    for gstin, inum, idt, val, txval, cgst, sgst, itcavl in records:
        sheet.append(
            [
                gstin,
                f"Supplier {gstin[:2]}",
                inum,
                "Regular",
                idt,
                val,
                f"{gstin[:2]}-State",
                "No",
                18,
                txval,
                0,
                cgst,
                sgst,
                0,
                "Yes" if itcavl == "Y" else "No",
            ]
        )
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def record_tuple(rec: GSTR2BRecord) -> tuple[Any, ...]:
    return (
        rec.supplier_gstin,
        rec.supplier_name,
        rec.invoice_number,
        rec.invoice_date,
        rec.invoice_value,
        rec.place_of_supply,
        rec.reverse_charge,
        rec.taxable_value,
        rec.igst,
        rec.cgst,
        rec.sgst,
        rec.cess,
        rec.itc_available,
    )


@pytest.fixture
def books(org_a):  # type: ignore[no-untyped-def]
    """Confirmed inward invoices for the period plus noise that must be ignored."""
    org = org_a.org
    parties = {
        S1: PartyFactory(org=org, gstin=S1, state_code="27"),
        S2: PartyFactory(org=org, gstin=S2, state_code="29"),
    }
    invoices = {
        number: InvoiceFactory(
            org=org,
            party=parties[gstin],
            direction="inward",
            status="confirmed",
            invoice_number=number,
            invoice_date=day,
            taxable_value=D(taxable),
            cgst=D(cgst),
            sgst=D(sgst),
            total=D(total),
        )
        for gstin, number, day, taxable, cgst, sgst, total in BOOKS
    }
    # Noise: needs_review, outward, and a party without a GSTIN are never candidates.
    InvoiceFactory(org=org, party=parties[S1], invoice_number="INV-011", status="needs_review")
    InvoiceFactory(
        org=org,
        party=parties[S1],
        invoice_number="INV-012",
        direction="outward",
        status="confirmed",
    )
    InvoiceFactory(org=org, party=PartyFactory(org=org, gstin=None), status="confirmed")
    return invoices


@pytest.fixture
def batch(org_a, books):  # type: ignore[no-untyped-def]
    return services.import_2b(
        org_a.org, data=json_2b(), filename="2b.json", period=PERIOD, actor=org_a.user
    )


# ---- import ----------------------------------------------------------------------------


def test_import_json_creates_batch_and_records(org_a, batch) -> None:  # type: ignore[no-untyped-def]
    assert batch.source == "json" and batch.period == PERIOD and batch.imported_by == org_a.user
    assert batch.records.count() == len(RECORDS_2B) and batch.counts == {"records": 8}
    rec = batch.records.get(invoice_number="INV-008")
    assert rec.supplier_gstin == S2 and rec.itc_available is False
    assert services.record_tax(rec) == D("450.00") and rec.place_of_supply == "29"
    audit = AuditEvent.objects.get(org=org_a.org, action="reconciliation.import_2b")
    assert audit.entity_id == batch.id and audit.after["records"] == 8


def test_json_and_excel_imports_produce_identical_records(org_a) -> None:  # type: ignore[no-untyped-def]
    from_json = services.import_2b(
        org_a.org, data=json_2b(), filename="2b.json", period=PERIOD, actor=org_a.user
    )
    from_xlsx = services.import_2b(
        org_a.org, data=excel_2b(), filename="2b.xlsx", period=PERIOD, actor=org_a.user
    )
    assert from_xlsx.source == "xlsx"
    rows_json = sorted(record_tuple(r) for r in from_json.records.all())
    rows_xlsx = sorted(record_tuple(r) for r in from_xlsx.records.all())
    assert rows_json == rows_xlsx and len(rows_json) == len(RECORDS_2B)


def test_detect_source_by_extension_then_by_magic() -> None:
    assert services.detect_source("x.JSON", b"[]") == "json"
    assert services.detect_source("x.xlsx", b"") == "xlsx"
    assert services.detect_source("upload", b"PK\x03\x04") == "xlsx"
    assert services.detect_source("upload", b'  {"data": {}}') == "json"
    with pytest.raises(services.ReconciliationError):
        services.detect_source("upload.csv", b"a,b")


@pytest.mark.parametrize(
    "data,filename,period,message",
    [
        (json_2b(), "2b.json", "2026-07", "MMYYYY"),
        (json_2b(), "2b.json", "082026", "period 072026"),
        (b"not json", "2b.json", PERIOD, "not valid JSON"),
        (json_2b(records=()), "2b.json", PERIOD, "no B2B invoices"),
        (b"PK\x03\x04junk", "2b.xlsx", PERIOD, "could not open"),
    ],
)
def test_import_rejects_bad_uploads(org_a, data, filename, period, message) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(services.ReconciliationError, match=message):
        services.import_2b(org_a.org, data=data, filename=filename, period=period)
    assert not GSTR2BBatch.objects.for_org(org_a.org).exists()


def test_import_rejects_workbook_without_b2b_sheet(org_a) -> None:  # type: ignore[no-untyped-def]
    workbook = Workbook()
    assert workbook.active is not None
    workbook.active.title = "Summary"
    buffer = BytesIO()
    workbook.save(buffer)
    with pytest.raises(services.ReconciliationError, match="no 'B2B' sheet"):
        services.import_2b(org_a.org, data=buffer.getvalue(), filename="2b.xlsx", period=PERIOD)


# ---- matching --------------------------------------------------------------------------


def test_seeded_fixture_classifies_into_all_five_types(org_a, batch, books) -> None:  # type: ignore[no-untyped-def]
    services.run_reconciliation(batch, actor=org_a.user)
    counts = {t: batch.matches.filter(match_type=t).count() for t in EXPECTED_COUNTS}
    assert counts == EXPECTED_COUNTS
    assert batch.counts["itc_at_risk"] == str(EXPECTED_AT_RISK)
    assert batch.counts["records"] == 8 and batch.counts["exact"] == 3

    by_record = {m.record.invoice_number: m for m in batch.matches.exclude(record=None)}
    assert by_record["INV/004"].match_type == "fuzzy"
    assert by_record["INV/004"].invoice == books["INV-004"]
    assert by_record["INV-005"].match_type == "fuzzy"
    assert by_record["INV-005"].invoice == books["INV-005"]
    mismatch = by_record["INV-006"]
    assert mismatch.match_type == "value_mismatch" and mismatch.invoice == books["INV-006"]
    assert (mismatch.delta_value, mismatch.delta_tax) == (D("500.00"), D("100.00"))
    assert services.match_at_risk(mismatch) == D("100.00")
    assert {by_record[n].invoice for n in ("INV-007", "INV-008")} == {None}
    missing_2b = {
        m.invoice.invoice_number for m in batch.matches.filter(match_type="missing_in_2b")
    }
    assert missing_2b == {"INV-009", "INV-010"}
    assert AuditEvent.objects.filter(org=org_a.org, action="reconciliation.run").count() == 1


def test_rerun_is_idempotent_and_replaces_matches(org_a, batch, books) -> None:  # type: ignore[no-untyped-def]
    services.run_reconciliation(batch)
    first_ids = set(batch.matches.values_list("id", flat=True))
    services.run_reconciliation(batch)
    assert batch.matches.count() == sum(EXPECTED_COUNTS.values())
    assert set(batch.matches.values_list("id", flat=True)).isdisjoint(first_ids)


def test_period_bounds_and_candidate_window(org_a, batch, books) -> None:  # type: ignore[no-untyped-def]
    assert services.period_bounds("022028") == (date(2028, 2, 1), date(2028, 2, 29))
    with pytest.raises(services.ReconciliationError):
        services.period_bounds("132026")
    numbers = {i.invoice_number for i in services.candidate_invoices(batch)}
    assert numbers == {n for _g, n, *_ in BOOKS}


def test_override_match_recomputes_deltas_and_audits(org_a, batch, books) -> None:  # type: ignore[no-untyped-def]
    services.run_reconciliation(batch)
    orphan = batch.matches.get(record__invoice_number="INV-007")
    match = services.override_match(
        orphan, actor=org_a.user, note="same doc", invoice=books["INV-009"]
    )
    assert match.invoice == books["INV-009"] and match.resolved_by == org_a.user
    assert match.match_type == "fuzzy"  # manual link defaults to fuzzy
    assert match.delta_value == D("5900") - D("7080")
    assert match.delta_tax == D("900") - D("1080")
    # the missing_in_2b placeholder for INV-009 is absorbed by the link
    assert batch.counts["fuzzy"] == 3 and batch.counts["missing_in_books"] == 1
    assert batch.counts["missing_in_2b"] == 1
    assert batch.counts["itc_at_risk"] == "550.00"
    event = AuditEvent.objects.get(org=org_a.org, action="reconciliation.override")
    assert event.before["match_type"] == "missing_in_books" and event.after["note"] == "same doc"

    with pytest.raises(services.ReconciliationError, match="already matched"):
        services.override_match(
            batch.matches.get(record__invoice_number="INV-008"),
            actor=org_a.user,
            invoice=books["INV-009"],
        )
    cleared = services.override_match(match, actor=org_a.user, clear_invoice=True)
    assert cleared.invoice is None and cleared.delta_value == D("0")
    assert cleared.match_type == "missing_in_books"
    # releasing the invoice puts its missing_in_2b row back
    assert batch.counts["missing_in_2b"] == 2 and batch.counts["itc_at_risk"] == "1450.00"
    placeholder = batch.matches.get(invoice=books["INV-009"])
    with pytest.raises(services.ReconciliationError, match="no record"):
        services.override_match(placeholder, actor=org_a.user, clear_invoice=True)
    relabelled = services.override_match(placeholder, actor=org_a.user, match_type="exact")
    assert relabelled.match_type == "exact" and relabelled.invoice == books["INV-009"]


def test_ims_accept_writes_audit_event(org_a, batch) -> None:  # type: ignore[no-untyped-def]
    rec = batch.records.get(invoice_number="INV-001")
    services.set_ims_action(rec, action="accept", note="matches books", actor=org_a.user)
    rec.refresh_from_db()
    assert rec.ims_action == "accept" and rec.ims_note == "matches books"
    event = AuditEvent.objects.get(org=org_a.org, action="ims.accept")
    assert event.entity_type == "GSTR2BRecord" and event.entity_id == rec.id
    assert event.actor == org_a.user
    assert event.before == {"ims_action": None, "ims_note": ""}
    assert event.after == {"ims_action": "accept", "ims_note": "matches books"}


# ---- API -------------------------------------------------------------------------------


def test_api_import_run_and_batch_detail(client_a, org_a, books) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post(
        "/api/reconciliation/import-2b/",
        {"file": SimpleUploadedFile("2b.json", json_2b()), "period": PERIOD},
        format="multipart",
    )
    assert r.status_code == 201, r.content
    batch_id = r.json()["id"]
    assert r.json()["imported_by"] == org_a.user.email

    r = client_a.post(f"/api/reconciliation/run/?batch={batch_id}")
    assert r.status_code == 200, r.content
    assert r.json()["counts"]["exact"] == 3

    r = client_a.get(f"/api/reconciliation/{batch_id}/")
    assert r.status_code == 200
    body = r.json()
    assert body["itc_at_risk"] == str(EXPECTED_AT_RISK)
    assert {t: len(rows) for t, rows in body["matches"].items()} == EXPECTED_COUNTS
    assert len(body["records"]) == 8
    running = [row["running_itc_at_risk"] for rows in body["matches"].values() for row in rows]
    assert running[-1] == str(EXPECTED_AT_RISK)
    mismatch = body["matches"]["value_mismatch"][0]
    assert mismatch["delta_value"] == "500.00" and mismatch["at_risk"] == "100.00"
    assert mismatch["invoice"]["invoice_number"] == "INV-006"
    assert mismatch["record"]["tax"] == "2700.00"

    # run by period picks the latest batch; list is filterable by period
    assert client_a.post(f"/api/reconciliation/run/?period={PERIOD}").status_code == 200
    assert client_a.post("/api/reconciliation/run/").status_code == 400
    assert client_a.post("/api/reconciliation/run/?period=082026").status_code == 404
    assert len(client_a.get(f"/api/reconciliation/?period={PERIOD}").json()["results"]) == 1
    assert client_a.get("/api/reconciliation/?period=082026").json()["results"] == []
    assert client_a.post("/api/reconciliation/", {}, format="json").status_code == 405


def test_api_import_validation_errors(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post(
        "/api/reconciliation/import-2b/",
        {"file": SimpleUploadedFile("2b.json", json_2b()), "period": "2026-07"},
        format="multipart",
    )
    assert r.status_code == 400 and "period" in r.json()["errors"]
    r = client_a.post(
        "/api/reconciliation/import-2b/",
        {"file": SimpleUploadedFile("2b.json", b"garbage"), "period": PERIOD},
        format="multipart",
    )
    assert r.status_code == 400 and "not valid JSON" in r.json()["detail"]
    assert (
        client_a.post("/api/reconciliation/import-2b/", {}, format="multipart").status_code == 400
    )


def test_api_match_patch_records_ims_and_filters(client_a, org_a, batch, books) -> None:  # type: ignore[no-untyped-def]
    services.run_reconciliation(batch)
    match = batch.matches.get(record__invoice_number="INV-006")
    r = client_a.patch(
        f"/api/reconciliation/matches/{match.id}/",
        {"match_type": "exact", "note": "credit note follows"},
        format="json",
    )
    assert r.status_code == 200, r.content
    assert r.json()["match_type"] == "exact" and r.json()["resolved_by"] == org_a.user.email
    assert (
        client_a.patch(f"/api/reconciliation/matches/{match.id}/", {}, format="json").status_code
        == 400
    )
    r = client_a.patch(
        f"/api/reconciliation/matches/{match.id}/",
        {"invoice": "00000000-0000-0000-0000-000000000000"},
        format="json",
    )
    assert r.status_code == 404

    exact = client_a.get(f"/api/reconciliation/matches/?batch={batch.id}&type=exact").json()
    assert len(exact["results"]) == 4  # 3 exact + the override above

    rec = batch.records.get(invoice_number="INV-007")
    r = client_a.post(
        f"/api/reconciliation/records/{rec.id}/ims/",
        {"action": "accept", "note": "will book it"},
        format="json",
    )
    assert r.status_code == 200 and r.json()["ims_action"] == "accept"
    assert AuditEvent.objects.filter(org=org_a.org, action="ims.accept").count() == 1
    r = client_a.post(f"/api/reconciliation/records/{rec.id}/ims/", {"action": "x"}, format="json")
    assert r.status_code == 400
    listed = client_a.get(f"/api/reconciliation/records/?batch={batch.id}").json()["results"]
    assert len(listed) == 8
    assert client_a.post("/api/reconciliation/records/", {}, format="json").status_code == 405


def test_cross_org_ids_are_404(client_b, org_a, batch, books) -> None:  # type: ignore[no-untyped-def]
    services.run_reconciliation(batch)
    match = batch.matches.first()
    rec = batch.records.first()
    assert match is not None and rec is not None
    assert client_b.get(f"/api/reconciliation/{batch.id}/").status_code == 404
    assert client_b.post(f"/api/reconciliation/run/?batch={batch.id}").status_code == 404
    assert (
        client_b.patch(
            f"/api/reconciliation/matches/{match.id}/", {"note": "x"}, format="json"
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            f"/api/reconciliation/records/{rec.id}/ims/", {"action": "accept"}, format="json"
        ).status_code
        == 404
    )
    assert client_b.get("/api/reconciliation/").json()["results"] == []
    assert ReconciliationMatch.objects.for_org(org_a.org).count() == batch.matches.count()


def test_viewer_reads_but_cannot_import_run_override_or_ims(  # type: ignore[no-untyped-def]
    viewer_client, org_a, batch, books
) -> None:
    services.run_reconciliation(batch)
    match = batch.matches.first()
    rec = batch.records.first()
    assert match is not None and rec is not None
    assert viewer_client.get(f"/api/reconciliation/{batch.id}/").status_code == 200
    r = viewer_client.post(
        "/api/reconciliation/import-2b/",
        {"file": SimpleUploadedFile("2b.json", json_2b()), "period": PERIOD},
        format="multipart",
    )
    assert r.status_code == 403
    assert viewer_client.post(f"/api/reconciliation/run/?batch={batch.id}").status_code == 403
    r = viewer_client.patch(
        f"/api/reconciliation/matches/{match.id}/", {"note": "x"}, format="json"
    )
    assert r.status_code == 403
    r = viewer_client.post(
        f"/api/reconciliation/records/{rec.id}/ims/", {"action": "accept"}, format="json"
    )
    assert r.status_code == 403
    # reviewer is not an import role either; accountant is.
    reviewer = client_for(MembershipFactory(org=org_a.org, role=Role.REVIEWER))
    assert reviewer.post(f"/api/reconciliation/run/?batch={batch.id}").status_code == 403
    accountant = client_for(MembershipFactory(org=org_a.org, role=Role.ACCOUNTANT))
    assert accountant.post(f"/api/reconciliation/run/?batch={batch.id}").status_code == 200
