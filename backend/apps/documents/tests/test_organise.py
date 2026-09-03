import io
import zipfile
from datetime import date

import pytest

from apps.documents.factories import DocumentFactory
from apps.documents.services.organise import safe_name
from apps.invoices.factories import InvoiceFactory
from apps.parties.factories import PartyFactory

pytestmark = pytest.mark.django_db


def test_safe_name_sanitises() -> None:
    assert (
        safe_name(date(2026, 7, 15), "Acme Widgets Pvt Ltd", "AW/25-26/0042", "application/pdf")
        == "2026-07-15_acme-widgets-pvt-ltd_AW-25-26-0042.pdf"
    )
    assert safe_name(date(2026, 7, 15), "../etc", "../../x", "image/png") == "2026-07-15_etc_x.png"


def test_zip_export_folders_and_collisions(client_a, org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_a.org, legal_name="Acme")
    twin = PartyFactory(org=org_a.org, legal_name="Acme")  # same slug, different party
    for i, (num, p) in enumerate([("A-1", party), ("A-1", twin), ("B-2", party)]):
        doc = DocumentFactory(org=org_a.org)
        fake_storage[doc.file] = b"%PDF-1.4 original " + str(i).encode()
        InvoiceFactory(
            org=org_a.org,
            party=p,
            document=doc,
            invoice_number=num,
            status="confirmed",
            invoice_date=date(2026, 7, 10),
            fy="2026-27",
            period_month="2026-07",
        )
    pending = DocumentFactory(org=org_a.org)
    fake_storage[pending.file] = b"%PDF"
    InvoiceFactory(
        org=org_a.org,
        party=party,
        document=pending,
        invoice_number="P-9",
        status="needs_review",
        period_month="2026-07",
    )
    r = client_a.get("/api/exports/documents.zip?period=2026-07")
    assert r.status_code == 200
    data = b"".join(r.streaming_content)
    names = sorted(zipfile.ZipFile(io.BytesIO(data)).namelist())
    assert names == [
        "FY2026-27/2026-07/2026-07-10_acme_A-1.pdf",
        "FY2026-27/2026-07/2026-07-10_acme_A-1_2.pdf",
        "FY2026-27/2026-07/2026-07-10_acme_B-2.pdf",
        "README.txt",
    ]
    # originals untouched
    assert fake_storage[pending.file] == b"%PDF"
    assert client_a.get("/api/exports/documents.zip?period=2025-01").status_code == 200
