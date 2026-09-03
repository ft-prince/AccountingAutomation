import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings

from apps.documents.factories import DocumentFactory
from apps.documents.models import DocumentStatus, ExtractionRun
from apps.documents.services import extraction
from apps.documents.services.extraction import ExtractionError, extract, has_text_layer
from apps.documents.services.schema import ExtractedInvoice
from apps.documents.tests.fakes import FakeAnthropic
from apps.documents.tests.pdfgen import build_pdf

FIXTURES = Path(settings.BASE_DIR) / "tests" / "fixtures" / "invoices"
CASES = sorted(p.stem.replace(".expected", "") for p in FIXTURES.glob("*.expected.json"))
pytestmark = pytest.mark.django_db


def _doc(org, fake_storage, name: str):  # type: ignore[no-untyped-def]
    data = (FIXTURES / f"{name}.pdf").read_bytes()
    doc = DocumentFactory(org=org, original_filename=f"{name}.pdf", size_bytes=len(data))
    fake_storage[doc.file] = data
    return doc


@pytest.mark.parametrize("name", CASES)
def test_golden_file(name: str, org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    doc = _doc(org_a.org, fake_storage, name)
    reply = json.loads((FIXTURES / f"{name}.reply.json").read_text())
    expected = json.loads((FIXTURES / f"{name}.expected.json").read_text())
    fake = FakeAnthropic([reply])

    run = extract(doc, client=fake)

    parsed = ExtractedInvoice.model_validate(run.parsed)
    assert parsed.supplier.gstin == expected["supplier_gstin"]
    assert parsed.recipient.gstin == expected["recipient_gstin"]
    assert parsed.invoice.number == expected["invoice_number"]
    assert parsed.invoice.date == expected["invoice_date"]
    assert len(parsed.lines) == expected["line_count"]
    for key, val in expected["totals"].items():
        assert getattr(parsed.totals, key) == Decimal(val), key
    got = [(i["code"], i["field"]) for i in run.validation_issues]
    assert got == [(i["code"], i["field"]) for i in expected["validation_issues"]]
    # Every numeric reached us as a string and became Decimal — never float.
    assert isinstance(parsed.lines[0].taxable_value, Decimal)
    assert run.input_tokens == 1200 and run.output_tokens == 300
    assert run.cost_inr == Decimal("1.1340")  # (1200*5 + 300*25)/1e6 USD * 84
    assert run.prompt_version == "extract_invoice_v1" and run.model_name == settings.ANTHROPIC_MODEL
    # The document went as a PDF document block (it has a text layer), and the tool was forced.
    call = fake.calls[0]
    assert call["messages"][0]["content"][0]["type"] == "document"
    assert call["tool_choice"] == {"type": "tool", "name": "record_invoice"}
    assert call["tools"][0]["strict"] is True


def test_schema_failure_retries_once_with_feedback_then_succeeds(org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    doc = _doc(org_a.org, fake_storage, "acme_intra_18")
    good = json.loads((FIXTURES / "acme_intra_18.reply.json").read_text())
    bad = {**good, "totals": {**good["totals"], "total": "thirty eight thousand"}}
    fake = FakeAnthropic([bad, good])
    run = extract(doc, client=fake)
    assert len(fake.calls) == 2
    assert "failed validation" in fake.calls[1]["messages"][0]["content"][-1]["text"]
    assert run.succeeded and run.input_tokens == 2400
    assert "first_attempt" in run.raw_response


def test_schema_failure_twice_records_failed_run(org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    doc = _doc(org_a.org, fake_storage, "acme_intra_18")
    fake = FakeAnthropic([None, None])
    with pytest.raises(ExtractionError):
        extract(doc, client=fake)
    run = ExtractionRun.objects.get(document=doc)
    assert "SchemaError" in run.error and run.parsed is None
    assert len(fake.calls) == 2


def test_float_in_money_field_is_rejected() -> None:
    good = json.loads((FIXTURES / "acme_intra_18.reply.json").read_text())
    good["totals"]["total"] = 38940.0
    with pytest.raises(ValueError, match="floats"):
        ExtractedInvoice.model_validate(good)


def test_extraction_run_is_append_only(org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    doc = _doc(org_a.org, fake_storage, "acme_intra_18")
    good = json.loads((FIXTURES / "acme_intra_18.reply.json").read_text())
    run = extract(doc, client=FakeAnthropic([good]))
    run.error = "tamper"
    with pytest.raises(ValueError, match="append-only"):
        run.save()


def test_scan_pdf_goes_as_page_images(org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    blank = build_pdf([])  # no text layer → scan path
    assert has_text_layer(blank) is False
    assert has_text_layer((FIXTURES / "acme_intra_18.pdf").read_bytes()) is True
    doc = DocumentFactory(org=org_a.org)
    fake_storage[doc.file] = blank
    good = json.loads((FIXTURES / "acme_intra_18.reply.json").read_text())
    fake = FakeAnthropic([good])
    extract(doc, client=fake)
    assert fake.calls[0]["messages"][0]["content"][0]["type"] == "image"


def test_task_wires_extraction_and_reextract_appends(
    client_a, org_a, fake_storage, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from apps.accounts.factories import GSTINProfileFactory

    GSTINProfileFactory(org=org_a.org, gstin="27AAGFF2194N1ZZ")
    doc = _doc(org_a.org, fake_storage, "acme_intra_18")
    good = json.loads((FIXTURES / "acme_intra_18.reply.json").read_text())
    monkeypatch.setattr(extraction, "_client", lambda: FakeAnthropic([good, good]))
    from apps.documents.tasks import extract_document

    assert extract_document.apply(args=[str(doc.pk)]).get() == "extracted"
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.EXTRACTED
    assert ExtractionRun.objects.filter(document=doc).count() == 1
    r = client_a.post(f"/api/documents/{doc.id}/reextract/")
    assert r.status_code == 202
    assert ExtractionRun.objects.filter(document=doc).count() == 2
    assert ExtractionRun.objects.filter(document=doc).exclude(error="").count() == 0
    from apps.invoices.models import Invoice

    assert Invoice.objects.filter(document=doc).count() == 2  # second run → duplicate
    assert Invoice.objects.filter(document=doc, status="duplicate").count() == 1
    from apps.invoices.models import Invoice

    assert Invoice.objects.filter(document=doc).count() == 2  # second is a duplicate
    assert Invoice.objects.filter(document=doc, status="duplicate").count() == 1


def test_api_key_never_in_run_or_error(org_a, fake_storage, settings) -> None:  # type: ignore[no-untyped-def]
    settings.ANTHROPIC_API_KEY = "sk-ant-SECRET"
    doc = _doc(org_a.org, fake_storage, "acme_intra_18")
    with pytest.raises(ExtractionError):
        extract(doc, client=FakeAnthropic([None, None]))
    run = ExtractionRun.objects.get(document=doc)
    assert "SECRET" not in json.dumps(run.raw_response) + run.error


@pytest.mark.live
def test_live_extraction(org_a, fake_storage) -> None:  # type: ignore[no-untyped-def]
    """Opt-in: pytest -m live. Needs ANTHROPIC_API_KEY in .env."""
    doc = _doc(org_a.org, fake_storage, "acme_intra_18")
    run = extract(doc)
    assert run.succeeded
    assert ExtractedInvoice.model_validate(run.parsed).supplier.gstin == "27AAPFU0939F1ZV"
