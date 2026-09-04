"""Manual entry and CSV import hold typed invoices to the same rules as extracted ones."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.factories import GSTINProfileFactory
from apps.core.audit import AuditEvent
from apps.invoices.manual import ManualInvoiceError, create_manual_invoice, csv_template, import_csv
from apps.invoices.models import Invoice
from apps.parties.factories import PartyFactory

pytestmark = pytest.mark.django_db
D = Decimal
OUR_GSTIN = "27AAGFF2194N1ZZ"


@pytest.fixture
def org_with_gstin(org_a):  # type: ignore[no-untyped-def]
    GSTINProfileFactory(org=org_a.org, gstin=OUR_GSTIN, state_code="27", is_default=True)
    return org_a


def _header(party, **over):  # type: ignore[no-untyped-def]
    return {
        "party": party.pk,
        "direction": "inward",
        "invoice_number": "PUR-001",
        "invoice_date": date(2026, 8, 15),
        **over,
    }


def test_totals_are_computed_not_accepted(org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_with_gstin.org, state_code="27", gstin="27AAPFU0939F1ZV")
    invoice = create_manual_invoice(
        org_with_gstin.org,
        _header(party),
        [
            {
                "description": "Sensor",
                "hsn_sac": "8543",
                "quantity": "8",
                "unit_price": "5000",
                "rate": "18",
            }
        ],
        actor=org_with_gstin.user,
    )
    # 40000 taxable, intra-state so each head is round(40000 * 18 / 200, 2)
    assert (invoice.taxable_value, invoice.cgst, invoice.sgst, invoice.igst) == (
        D("40000.00"),
        D("3600.00"),
        D("3600.00"),
        D("0.00"),
    )
    assert invoice.total == D("47200.00") and invoice.supply_type == "intra"
    assert invoice.status == "needs_review" and invoice.confidence == D("1.000")
    assert invoice.fy == "2026-27" and invoice.period_month == "2026-08"
    assert AuditEvent.objects.filter(entity_id=invoice.pk, action="invoice.manual_create").exists()


def test_inter_state_goes_to_igst(org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_with_gstin.org, state_code="29", gstin="29AABCT1332L1ZA")
    invoice = create_manual_invoice(
        org_with_gstin.org,
        _header(party, place_of_supply_state_code="27"),
        [
            {
                "description": "Cloud",
                "hsn_sac": "998315",
                "quantity": "1",
                "unit_price": "40000",
                "rate": "18",
            }
        ],
        actor=org_with_gstin.user,
    )
    assert invoice.igst == D("7200.00") and invoice.cgst == 0 and invoice.supply_type == "inter"


def test_validation_issues_are_recorded(org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(
        org=org_with_gstin.org, state_code="27", gstin=None, legal_name="Cash Vendor"
    )
    invoice = create_manual_invoice(
        org_with_gstin.org,
        _header(party),
        [
            {
                "description": "Sundry",
                "hsn_sac": "9999",
                "quantity": "1",
                "unit_price": "100",
                "rate": "18",
            }
        ],
        actor=org_with_gstin.user,
    )
    assert invoice.issues.exists()  # no supplier GSTIN on an inward bill is a Rule 46 problem


def test_guards(org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    org = org_with_gstin.org
    party = PartyFactory(org=org, state_code="27")
    line = [{"description": "x", "quantity": "1", "unit_price": "100", "rate": "18"}]
    with pytest.raises(ManualInvoiceError, match="At least one line"):
        create_manual_invoice(org, _header(party), [], actor=org_with_gstin.user)
    with pytest.raises(ManualInvoiceError, match="Unknown party"):
        create_manual_invoice(
            org,
            {**_header(party), "party": None},
            line,
            actor=org_with_gstin.user,
        )
    create_manual_invoice(org, _header(party), line, actor=org_with_gstin.user)
    with pytest.raises(ManualInvoiceError, match="already exists"):
        create_manual_invoice(org, _header(party), line, actor=org_with_gstin.user)
    with pytest.raises(ManualInvoiceError, match="not a number"):
        create_manual_invoice(
            org,
            _header(party, invoice_number="PUR-002"),
            [{**line[0], "unit_price": "abc"}],
            actor=org_with_gstin.user,
        )


def test_api_create_and_role_gate(client_a, viewer_client, org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_with_gstin.org, state_code="27", gstin="27AAPFU0939F1ZV")
    body = {
        "party": str(party.pk),
        "direction": "inward",
        "invoice_number": "API-001",
        "invoice_date": "2026-08-15",
        "lines": [
            {
                "description": "Sensor",
                "hsn_sac": "8543",
                "quantity": "2",
                "unit_price": "617.28",
                "rate": "5",
            }
        ],
    }
    assert viewer_client.post("/api/invoices/", body, format="json").status_code == 403
    r = client_a.post("/api/invoices/", body, format="json")
    assert r.status_code == 201, r.json()
    # 5% intra on 1234.56 rounds each head independently
    assert r.json()["cgst"] == "30.86" and r.json()["sgst"] == "30.86"
    assert r.json()["taxable_value"] == "1234.56" and r.json()["total"] == "1296.00"
    assert r.json()["lines"][0]["line_total"] == "1296.28"
    bad = client_a.post("/api/invoices/", {**body, "lines": []}, format="json")
    assert bad.status_code == 400


def test_csv_import_groups_rows_into_invoices(client_a, org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    PartyFactory(
        org=org_with_gstin.org,
        state_code="27",
        gstin="27AAPFU0939F1ZV",
        legal_name="Acme Widgets Pvt Ltd",
    )
    csv_text = (
        "invoice_number,invoice_date,direction,party_gstin,description,hsn_sac,quantity,uom,unit_price,discount,rate,cess_rate\n"
        "CSV-001,2026-08-15,inward,27AAPFU0939F1ZV,Sensor,8543,8,nos,5000,0,18,0\n"
        "CSV-001,2026-08-15,inward,27AAPFU0939F1ZV,Install,998719,1,nos,8000,0,18,0\n"
        "CSV-002,2026-08-16,inward,27AAPFU0939F1ZV,Cable,8544,10,nos,250,0,18,0\n"
        "CSV-003,2026-08-17,inward,99UNKNOWN0000Z,Ghost,8544,1,nos,100,0,18,0\n"
    )
    r = client_a.post(
        "/api/invoices/import/", {"file": SimpleUploadedFile("in.csv", csv_text.encode())}
    )
    assert r.status_code == 207, r.json()
    body = r.json()
    assert body["invoices"] == 2 and body["failed"] == 1
    assert body["errors"][0]["invoice_number"] == "CSV-003"
    first = Invoice.objects.get(org=org_with_gstin.org, invoice_number="CSV-001")
    assert (
        first.lines.count() == 2
        and first.taxable_value == D("48000.00")
        and first.total == D("56640.00")
    )


def test_csv_missing_columns_rejected(client_a, org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post(
        "/api/invoices/import/", {"file": SimpleUploadedFile("x.csv", b"foo,bar\n1,2\n")}
    )
    assert r.status_code == 400 and "missing required columns" in str(r.json()).lower()


def test_template_downloads_and_round_trips(client_a, org_with_gstin) -> None:  # type: ignore[no-untyped-def]
    PartyFactory(
        org=org_with_gstin.org,
        state_code="27",
        gstin="27AAPFU0939F1ZV",
        legal_name="Acme Widgets Pvt Ltd",
    )
    r = client_a.get("/api/invoices/import-template/")
    assert r.status_code == 200 and r["Content-Type"] == "text/csv"
    result = import_csv(org_with_gstin.org, csv_template().encode(), actor=org_with_gstin.user)
    assert result["invoices"] == 1 and result["failed"] == 0
