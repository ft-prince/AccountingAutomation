"""GSTR-1 / GSTR-3B JSON and accounting CSV exports (PROJECT_SPECS §3.6, §7.1, §10, §13).

Every export is built from CONFIRMED invoices only; needs_review rows are counted in the
X-Pending-Count header and never appear in the payload. Structural validation here uses
the bundled schemas; validation in the real GSTN offline tool is a manual owner step.
"""

import csv
import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum

from apps.accounts.factories import GSTINProfileFactory
from apps.gst.exports import validate as validator
from apps.gst.exports.common import ExportError, dumps, money, period_month, to_json
from apps.gst.exports.csv import build_csv, date_range_from_params
from apps.gst.exports.gstr1 import B2CL_THRESHOLD, build_gstr1
from apps.gst.exports.gstr3b import build_gstr3b
from apps.invoices.factories import InvoiceFactory, LineFactory
from apps.invoices.models import Invoice
from apps.parties.factories import CategoryFactory, PartyFactory

pytestmark = pytest.mark.django_db
D = Decimal
PERIOD = "072026"
S1 = "27AABCT1332L1ZU"
S2 = "29AAACR5055K1Z7"
GSTN_DATE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
GSTR1_KEYS = {
    "gstin",
    "fp",
    "gt",
    "cur_gt",
    "b2b",
    "b2cl",
    "b2cs",
    "cdnr",
    "exp",
    "hsn",
    "nil",
    "doc_issue",
}
B2B_INV_KEYS = {"inum", "idt", "val", "pos", "rchrg", "inv_typ", "itms"}
ITM_DET_KEYS = {"rt", "txval", "iamt", "camt", "samt", "csamt"}
NO_TAX = {"cgst": D("0"), "sgst": D("0"), "igst": D("0")}


def outward_invoice(org: Any, party: Any, number: str, day: int, **kw: Any) -> Invoice:
    fields: dict[str, Any] = {
        "org": org,
        "party": party,
        "direction": "outward",
        "status": "confirmed",
        "invoice_number": number,
        "invoice_date": date(2026, 7, day),
        **kw,
    }
    return InvoiceFactory(**fields)


def igst_line(invoice: Invoice, hsn: str, taxable: str, igst: str, rate: str = "18") -> None:
    LineFactory(
        invoice=invoice,
        hsn_sac=hsn,
        unit_price=D(taxable),
        taxable_value=D(taxable),
        rate=D(rate),
        cgst=D("0"),
        sgst=D("0"),
        igst=D(igst),
        line_total=D(taxable) + D(igst),
    )


@pytest.fixture
def profile(org_a):  # type: ignore[no-untyped-def]
    return GSTINProfileFactory(org=org_a.org, is_default=True)


@pytest.fixture
def outward(org_a, profile):  # type: ignore[no-untyped-def]
    """Four confirmed outward invoices: B2B intra, B2B inter, B2C inter > threshold, export."""
    org = org_a.org
    reg_intra = PartyFactory(org=org, gstin=S1, state_code="27")
    reg_inter = PartyFactory(org=org, gstin=S2, state_code="29")
    consumer = PartyFactory(org=org, gstin=None, state_code="29")
    overseas = PartyFactory(org=org, gstin=None, state_code="")

    b2b_intra = outward_invoice(org, reg_intra, "NX-001", 3)
    LineFactory(invoice=b2b_intra)
    b2b_inter = outward_invoice(
        org,
        reg_inter,
        "NX-002",
        10,
        supply_type="inter",
        place_of_supply_state_code="29",
        taxable_value=D("20000"),
        igst=D("3600"),
        total=D("23600"),
        **{k: v for k, v in NO_TAX.items() if k != "igst"},
    )
    igst_line(b2b_inter, "8471", "20000", "3600")
    b2cl = outward_invoice(
        org,
        consumer,
        "NX-003",
        15,
        supply_type="inter",
        taxable_value=D("200000"),
        igst=D("36000"),
        total=D("236000"),
        **{k: v for k, v in NO_TAX.items() if k != "igst"},
    )
    igst_line(b2cl, "8471", "200000", "36000")
    export = outward_invoice(
        org,
        overseas,
        "NX-004",
        20,
        supply_type="export",
        taxable_value=D("50000"),
        total=D("50000"),
        **NO_TAX,
    )
    igst_line(export, "9983", "50000", "0", rate="0")
    # Excluded: needs_review outward, confirmed inward.
    outward_invoice(org, reg_intra, "NX-005", 25, status="needs_review", taxable_value=D("99999"))
    InvoiceFactory(org=org, party=reg_intra, status="confirmed", invoice_number="VN-001")
    return {"b2b_intra": b2b_intra, "b2b_inter": b2b_inter, "b2cl": b2cl, "export": export}


# ---- GSTR-1 ----------------------------------------------------------------------------


def test_gstr1_key_structure_and_sections(org_a, profile, outward) -> None:  # type: ignore[no-untyped-def]
    payload = build_gstr1(org_a.org, PERIOD)
    assert set(payload) == GSTR1_KEYS
    assert payload["gstin"] == profile.gstin and payload["fp"] == PERIOD

    assert [s["ctin"] for s in payload["b2b"]] == [S1, S2]
    intra = payload["b2b"][0]["inv"][0]
    assert set(intra) == B2B_INV_KEYS and set(intra["itms"][0]["itm_det"]) == ITM_DET_KEYS
    assert (intra["inum"], intra["idt"], intra["pos"]) == ("NX-001", "03-07-2026", "27")
    assert intra["rchrg"] == "N" and intra["inv_typ"] == "R" and intra["val"] == D("11800.00")
    assert intra["itms"][0]["itm_det"]["rt"] == 18
    assert intra["itms"][0]["itm_det"]["camt"] == D("900.00")
    inter = payload["b2b"][1]["inv"][0]
    assert inter["pos"] == "29" and inter["itms"][0]["itm_det"]["iamt"] == D("3600.00")

    assert payload["b2cl"] == [
        {
            "pos": "29",
            "inv": [
                {
                    "inum": "NX-003",
                    "idt": "15-07-2026",
                    "val": D("236000.00"),
                    "itms": [
                        {
                            "num": 1,
                            "itm_det": {
                                "rt": 18,
                                "txval": D("200000.00"),
                                "iamt": D("36000.00"),
                                "csamt": D("0.00"),
                            },
                        }
                    ],
                }
            ],
        }
    ]
    assert payload["b2cs"] == [] and payload["cdnr"] == []
    (exp_group,) = payload["exp"]
    assert exp_group["exp_typ"] == "WOPAY"
    (exp_inv,) = exp_group["inv"]
    assert exp_inv["inum"] == "NX-004" and exp_inv["sbnum"] == "" and exp_inv["sbdt"] == ""
    assert exp_inv["itms"] == [
        {"txval": D("50000.00"), "rt": 0, "iamt": D("0.00"), "csamt": D("0.00")}
    ]

    hsn = {(row["hsn_sc"], row["rt"]): row for row in payload["hsn"]["data"]}
    assert set(hsn) == {("8471", 18), ("8543", 18), ("9983", 0)}
    assert hsn[("8471", 18)]["txval"] == D("220000.00") and hsn[("8471", 18)]["qty"] == D("2")
    assert [row["num"] for row in payload["hsn"]["data"]] == [1, 2, 3]
    assert [row["sply_ty"] for row in payload["nil"]["inv"]] == [
        "INTRB2B",
        "INTRB2C",
        "INTRAB2B",
        "INTRAB2C",
    ]
    (doc,) = payload["doc_issue"]["doc_det"][0]["docs"]
    assert doc == {
        "num": 1,
        "totnum": 4,
        "cancel": 0,
        "net_issue": 4,
        "from": "NX-001",
        "to": "NX-004",
    }
    assert payload["cur_gt"] == D("321400.00") and payload["gt"] == D("0.00")


def test_gstr1_b2b_taxable_equals_db_sum_and_excludes_needs_review(  # type: ignore[no-untyped-def]
    org_a, profile, outward
) -> None:
    payload = build_gstr1(org_a.org, PERIOD)
    b2b_txval = sum(
        it["itm_det"]["txval"]
        for supplier in payload["b2b"]
        for inv in supplier["inv"]
        for it in inv["itms"]
    )
    db_sum = Invoice.objects.filter(
        org=org_a.org, status="confirmed", direction="outward", party__gstin__isnull=False
    ).aggregate(s=Sum("taxable_value"))["s"]
    assert b2b_txval == db_sum == D("30000.00")
    serialised = dumps(payload)
    assert "NX-005" not in serialised and "VN-001" not in serialised and "99999" not in serialised
    dates = [
        inv["idt"]
        for section in ("b2b", "b2cl", "exp")
        for g in payload[section]
        for inv in g["inv"]
    ]
    assert dates and all(GSTN_DATE.match(d) for d in dates)


def test_gstr1_validates_against_bundled_schema_with_number_amounts(  # type: ignore[no-untyped-def]
    org_a, profile, outward
) -> None:
    payload = to_json(build_gstr1(org_a.org, PERIOD))
    assert validator.validate(payload, validator.load_schema("gstr1_v4_1.json")) == []
    assert payload["b2b"][0]["inv"][0]["val"] == 11800.0
    assert isinstance(payload["b2b"][0]["inv"][0]["val"], float)
    assert isinstance(payload["b2b"][0]["inv"][0]["itms"][0]["itm_det"]["rt"], int)


def test_gstr1_b2cs_sez_threshold_and_header_only_rate(org_a, profile) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    walk_in = PartyFactory(org=org, gstin=None, state_code="27")
    far_consumer = PartyFactory(org=org, gstin=None, state_code="29")
    sez = PartyFactory(org=org, gstin=S2, state_code="29")
    # two B2C intra invoices at one rate aggregate into one b2cs row (header-only: rate derived)
    outward_invoice(
        org, walk_in, "C-1", 1, taxable_value=D("1000"), cgst=D("90"), sgst=D("90"), total=D("1180")
    )
    outward_invoice(
        org,
        walk_in,
        "C-2",
        2,
        taxable_value=D("2000"),
        cgst=D("180"),
        sgst=D("180"),
        total=D("2360"),
    )
    # B2C inter at exactly the threshold stays in b2cs; one rupee over goes to b2cl
    at = B2CL_THRESHOLD
    outward_invoice(
        org,
        far_consumer,
        "C-3",
        3,
        supply_type="inter",
        taxable_value=at,
        igst=D("0"),
        total=at,
        cgst=D("0"),
        sgst=D("0"),
    )
    outward_invoice(
        org,
        far_consumer,
        "C-4",
        4,
        supply_type="inter",
        taxable_value=at + 1,
        igst=D("0"),
        total=at + 1,
        cgst=D("0"),
        sgst=D("0"),
    )
    outward_invoice(
        org,
        sez,
        "S-1",
        5,
        supply_type="sez",
        taxable_value=D("1000"),
        igst=D("180"),
        total=D("1180"),
        cgst=D("0"),
        sgst=D("0"),
    )
    outward_invoice(
        org,
        sez,
        "S-2",
        6,
        supply_type="sez",
        taxable_value=D("1000"),
        igst=D("0"),
        total=D("1000"),
        cgst=D("0"),
        sgst=D("0"),
        is_reverse_charge=True,
    )

    payload = build_gstr1(org, PERIOD)
    assert payload["b2cs"] == [
        {
            "sply_ty": "INTER",
            "pos": "29",
            "typ": "OE",
            "rt": 0,
            "txval": at,
            "iamt": D("0.00"),
            "camt": D("0.00"),
            "samt": D("0.00"),
            "csamt": D("0.00"),
        },
        {
            "sply_ty": "INTRA",
            "pos": "27",
            "typ": "OE",
            "rt": 18,
            "txval": D("3000.00"),
            "iamt": D("0.00"),
            "camt": D("270.00"),
            "samt": D("270.00"),
            "csamt": D("0.00"),
        },
    ]
    assert [inv["inum"] for g in payload["b2cl"] for inv in g["inv"]] == ["C-4"]
    sez_rows = {inv["inum"]: inv for inv in payload["b2b"][0]["inv"]}
    assert sez_rows["S-1"]["inv_typ"] == "SEZWP" and sez_rows["S-2"]["inv_typ"] == "SEZWOP"
    assert sez_rows["S-2"]["rchrg"] == "Y"
    assert payload["hsn"]["data"] == []  # header-only invoices carry no HSN
    assert validator.validate(to_json(payload), validator.load_schema("gstr1_v4_1.json")) == []


def test_gstr1_errors(org_a) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ExportError, match="no GSTIN profile"):
        build_gstr1(org_a.org, PERIOD)
    GSTINProfileFactory(org=org_a.org)
    with pytest.raises(ExportError, match="MMYYYY"):
        build_gstr1(org_a.org, "2026-07")
    assert period_month("032027") == "2027-03"
    assert money(None) == D("0.00") and money(D("1.005")) == D("1.01")


# ---- GSTR-3B ---------------------------------------------------------------------------


@pytest.fixture
def three_b(org_a, profile):  # type: ignore[no-untyped-def]
    org = org_a.org
    vendor = PartyFactory(org=org, gstin=S1, state_code="27")
    consumer = PartyFactory(org=org, gstin=None, state_code="29")
    composition = PartyFactory(org=org, gstin=S2, state_code="29", is_composition=True)
    overseas = PartyFactory(org=org, gstin=None, state_code="")
    inward = dict(org=org, party=vendor, direction="inward", status="confirmed")
    InvoiceFactory(**inward, invoice_number="P-OTH")
    InvoiceFactory(
        **inward,
        invoice_number="P-RCM",
        is_reverse_charge=True,
        taxable_value=D("5000"),
        cgst=D("450"),
        sgst=D("450"),
        total=D("5900"),
    )
    InvoiceFactory(
        **inward,
        invoice_number="P-BLOCKED",
        itc_eligible=False,
        itc_blocked_reason="17(5)(b) food",
        taxable_value=D("2000"),
        cgst=D("180"),
        sgst=D("180"),
        total=D("2360"),
    )
    InvoiceFactory(
        **inward,
        invoice_number="P-IMPORT",
        supply_type="import",
        taxable_value=D("20000"),
        igst=D("3600"),
        cgst=D("0"),
        sgst=D("0"),
        total=D("23600"),
    )
    InvoiceFactory(**{**inward, "status": "needs_review"}, invoice_number="P-PENDING")
    outward_invoice(org, vendor, "O-INTRA", 1)
    outward_invoice(
        org,
        consumer,
        "O-UNREG",
        2,
        supply_type="inter",
        taxable_value=D("30000"),
        igst=D("5400"),
        cgst=D("0"),
        sgst=D("0"),
        total=D("35400"),
    )
    outward_invoice(
        org,
        composition,
        "O-COMP",
        3,
        supply_type="inter",
        taxable_value=D("4000"),
        igst=D("720"),
        cgst=D("0"),
        sgst=D("0"),
        total=D("4720"),
    )
    outward_invoice(
        org,
        overseas,
        "O-EXP",
        4,
        supply_type="export",
        taxable_value=D("50000"),
        total=D("50000"),
        **NO_TAX,
    )


def _heads(rows: list[dict[str, Any]]) -> dict[str, dict[str, Decimal]]:
    return {row["ty"]: {k: v for k, v in row.items() if k != "ty"} for row in rows}


def test_gstr3b_mapping_and_itc_net_arithmetic(org_a, profile, three_b) -> None:  # type: ignore[no-untyped-def]
    payload = build_gstr3b(org_a.org, PERIOD)
    assert payload["gstin"] == profile.gstin and payload["ret_period"] == PERIOD
    sup = payload["sup_details"]
    assert sup["osup_det"] == {
        "txval": D("44000.00"),
        "iamt": D("6120.00"),
        "camt": D("900.00"),
        "samt": D("900.00"),
        "csamt": D("0.00"),
    }
    assert sup["osup_zero"] == {"txval": D("50000.00"), "iamt": D("0.00"), "csamt": D("0.00")}
    assert sup["isup_rev"] == {
        "txval": D("5000.00"),
        "iamt": D("0.00"),
        "camt": D("450.00"),
        "samt": D("450.00"),
        "csamt": D("0.00"),
    }
    assert payload["inter_sup"]["unreg_details"] == [
        {"pos": "29", "txval": D("30000.00"), "iamt": D("5400.00")}
    ]
    assert payload["inter_sup"]["comp_details"] == [
        {"pos": "29", "txval": D("4000.00"), "iamt": D("720.00")}
    ]
    assert payload["inter_sup"]["uin_details"] == []

    itc = payload["itc_elg"]
    avl = _heads(itc["itc_avl"])
    assert list(avl) == ["IMPG", "IMPS", "ISRC", "ISD", "OTH"]
    assert avl["IMPG"]["iamt"] == D("3600.00") and avl["IMPG"]["camt"] == D("0.00")
    assert avl["ISRC"] == {
        "iamt": D("0.00"),
        "camt": D("450.00"),
        "samt": D("450.00"),
        "csamt": D("0.00"),
    }
    assert avl["OTH"] == {
        "iamt": D("0.00"),
        "camt": D("900.00"),
        "samt": D("900.00"),
        "csamt": D("0.00"),
    }
    rev = _heads(itc["itc_rev"])
    assert list(rev) == ["RUL", "OTH"]
    expected_net = {
        k: sum(h[k] for h in avl.values()) - sum(h[k] for h in rev.values())
        for k in ("iamt", "camt", "samt", "csamt")
    }
    assert itc["itc_net"] == expected_net
    assert itc["itc_net"] == {
        "iamt": D("3600.00"),
        "camt": D("1350.00"),
        "samt": D("1350.00"),
        "csamt": D("0.00"),
    }
    inelg = _heads(itc["itc_inelg"])
    assert inelg["RUL"] == {
        "iamt": D("0.00"),
        "camt": D("180.00"),
        "samt": D("180.00"),
        "csamt": D("0.00"),
    }
    # the blocked invoice's tax appears in 4(D) only, never in 4(A)
    assert sum(h["camt"] for h in avl.values()) == D("1350.00")
    assert validator.validate(to_json(payload), validator.load_schema("gstr3b_v1_1.json")) == []


# ---- HTTP ------------------------------------------------------------------------------


def test_export_endpoints_confirmed_only_with_pending_header(
    client_a, org_a, profile, outward
) -> None:  # type: ignore[no-untyped-def]
    r = client_a.get(f"/api/exports/gstr1?period={PERIOD}")
    assert r.status_code == 200 and r["Content-Type"] == "application/json"
    assert r["Content-Disposition"] == f'attachment; filename="GSTR1_{profile.gstin}_{PERIOD}.json"'
    assert r["X-Pending-Count"] == "1"
    body = json.loads(r.content)
    validator.assert_valid(body, "gstr1_v4_1.json")
    assert body["b2b"][0]["inv"][0]["val"] == 11800.0

    r = client_a.get(f"/api/exports/gstr3b?period={PERIOD}")
    assert r.status_code == 200 and r["X-Pending-Count"] == "1"
    validator.assert_valid(json.loads(r.content), "gstr3b_v1_1.json")
    assert json.loads(r.content)["sup_details"]["osup_det"]["txval"] == 230000.0

    assert client_a.get("/api/exports/gstr1?period=13-2026").status_code == 400
    assert client_a.get("/api/exports/gstr1").status_code == 400
    assert client_a.get("/api/exports/nope?period=072026").status_code == 404


def test_export_without_gstin_profile_is_400(client_a) -> None:  # type: ignore[no-untyped-def]
    r = client_a.get(f"/api/exports/gstr1?period={PERIOD}")
    assert r.status_code == 400 and "GSTIN profile" in r.json()["detail"]


def test_exports_are_isolated_per_org(client_b, org_a, org_b, profile, outward) -> None:  # type: ignore[no-untyped-def]
    GSTINProfileFactory(org=org_b.org, gstin="29AAACR5055K1Z7")
    body = json.loads(client_b.get(f"/api/exports/gstr1?period={PERIOD}").content)
    assert body["b2b"] == [] and body["b2cl"] == [] and body["exp"] == []
    assert body["doc_issue"]["doc_det"][0]["docs"][0]["totnum"] == 0


def test_viewer_can_export(viewer_client, org_a, profile, outward) -> None:  # type: ignore[no-untyped-def]
    assert viewer_client.get(f"/api/exports/gstr1?period={PERIOD}").status_code == 200
    assert viewer_client.get("/api/exports/csv?type=tally&fy=2026-27").status_code == 200


# ---- CSV -------------------------------------------------------------------------------


@pytest.fixture
def ledgers(org_a):  # type: ignore[no-untyped-def]
    org = org_a.org
    vendor = PartyFactory(org=org, gstin=S1, state_code="27", legal_name="Acme Tools Pvt Ltd")
    software = CategoryFactory(
        org=org, name="Software & SaaS", tally_ledger_name="Software Expenses"
    )
    bill = InvoiceFactory(
        org=org, party=vendor, status="confirmed", invoice_number="B-1", notes="UTR 123"
    )
    LineFactory(invoice=bill, category=software)
    sale = outward_invoice(org, vendor, "S-1", 9)
    LineFactory(invoice=sale, description="Consulting", hsn_sac="9983")
    InvoiceFactory(org=org, party=vendor, status="needs_review", invoice_number="B-2")
    InvoiceFactory(
        org=org,
        party=vendor,
        status="confirmed",
        invoice_number="B-OLD",
        invoice_date=date(2025, 3, 1),
        fy="2024-25",
        period_month="2025-03",
    )
    return {"bill": bill, "sale": sale}


def _rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(content.decode().splitlines()))


def test_csv_tally_rows_carry_category_ledger(client_a, org_a, ledgers) -> None:  # type: ignore[no-untyped-def]
    r = client_a.get("/api/exports/csv?type=tally&fy=2026-27")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    assert r["X-Pending-Count"] == "1"
    assert r["Content-Disposition"] == 'attachment; filename="tally_2026-04-01_2027-03-31.csv"'
    header, *rows = _rows(r.content)
    assert header == [
        "Date",
        "Voucher Type",
        "Party Ledger",
        "Ledger",
        "Amount",
        "CGST",
        "SGST",
        "IGST",
        "Narration",
        "Invoice No",
    ]
    by_number = {row[-1]: row for row in rows}
    assert set(by_number) == {"B-1", "S-1"}  # B-2 pending, B-OLD outside the FY
    assert by_number["B-1"][:5] == [
        "15-07-2026",
        "Purchase",
        "Acme Tools Pvt Ltd",
        "Software Expenses",
        "10000.00",
    ]
    assert by_number["B-1"][8] == "UTR 123"
    assert (
        by_number["S-1"][1] == "Sales" and by_number["S-1"][3] == "Sales"
    )  # no category → voucher ledger


def test_csv_zoho_raw_and_range_params(client_a, org_a, ledgers) -> None:  # type: ignore[no-untyped-def]
    r = client_a.get("/api/exports/csv?type=zoho&fy=2026-27")
    header, *rows = _rows(r.content)
    assert header[:3] == ["Invoice Date", "Invoice Number", "Customer Name"]
    zoho = {row[1]: row for row in rows}
    assert zoho["S-1"][3] == "business_gst" and zoho["S-1"][6] == "Consulting"
    assert zoho["S-1"][10] == "GST18" and zoho["S-1"][11] == "18"

    r = client_a.get("/api/exports/csv?type=raw&from=2026-07-01&to=2026-07-10")
    header, *rows = _rows(r.content)
    assert "invoice_number" in header and "line_category_name" in header
    assert [row[header.index("invoice_number")] for row in rows] == ["S-1"]
    assert r["X-Pending-Count"] == "0"

    assert client_a.get("/api/exports/csv?type=quickbooks").status_code == 400
    assert client_a.get("/api/exports/csv?type=tally&fy=26-27").status_code == 400
    assert (
        client_a.get("/api/exports/csv?type=tally&from=2026-08-01&to=2026-07-01").status_code == 400
    )


def test_build_csv_and_date_range_defaults(org_a, ledgers) -> None:  # type: ignore[no-untyped-def]
    rng = date_range_from_params({}, today=date(2026, 9, 4))
    assert (rng.start, rng.end) == (date(2026, 4, 1), date(2027, 3, 31))
    export = build_csv(org_a.org, "tally", {"fy": "2024-25"})
    assert export.invoice_count == 1 and export.pending == 0
    assert export.filename == "tally_2024-04-01_2025-03-31.csv"
    with pytest.raises(ExportError):
        date_range_from_params({"from": "yesterday"})


# ---- validator -------------------------------------------------------------------------


def test_structural_validator_reports_each_violation() -> None:
    schema = {
        "type": "object",
        "required": ["gstin", "rows"],
        "additionalProperties": False,
        "properties": {
            "gstin": {"type": "string"},
            "rate": {"type": ["integer", "number"]},
            "kind": {"type": "string", "enum": ["R", "DE"]},
            "rows": {"type": "array", "items": {"$ref": "#/definitions/row"}},
        },
        "definitions": {
            "row": {
                "type": "object",
                "required": ["val"],
                "properties": {"val": {"type": "number"}},
            }
        },
    }
    assert validator.validate({"gstin": "x", "rows": [{"val": 1.5}], "rate": 18}, schema) == []
    errors = validator.validate(
        {"gstin": 1, "rate": True, "kind": "Z", "extra": 1, "rows": [{"val": "no"}, 3]}, schema
    )
    assert errors == [
        "$.gstin: expected string, got int",
        "$.rate: expected ['integer', 'number'], got bool",
        "$.kind: 'Z' not in ['R', 'DE']",
        "$: unexpected key 'extra'",
        "$.rows[0].val: expected number, got str",
        "$.rows[1]: expected object, got int",
    ]
    assert validator.validate({"rows": []}, schema) == ["$: missing required key 'gstin'"]
    with pytest.raises(ValueError, match="unresolvable"):
        validator.validate({}, {"$ref": "#/definitions/missing", "definitions": {}})
    with pytest.raises(ValueError, match="only local"):
        validator.validate({}, {"$ref": "http://example.com/schema"})
    with pytest.raises(ValueError, match="schema object"):
        validator.validate({}, {"$ref": "#/definitions/leaf", "definitions": {"leaf": 1}})
    with pytest.raises(ValueError, match="missing required key"):
        validator.assert_valid({}, "gstr3b_v1_1.json")
