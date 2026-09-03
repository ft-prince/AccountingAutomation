import io
import zipfile
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents import storage
from apps.documents.factories import DocumentFactory
from apps.documents.models import Document, DocumentStatus
from apps.documents.services import MAX_BYTES, UploadError, ingest_bytes
from apps.documents.tasks import extract_document

pytestmark = pytest.mark.django_db


def _upload(client, name: str, data: bytes, ct: str = "application/pdf"):  # type: ignore[no-untyped-def]
    return client.post("/api/documents/", {"file": SimpleUploadedFile(name, data, ct)})


def test_upload_creates_pending_document_and_queues(client_a, pdf_bytes, fake_storage) -> None:  # type: ignore[no-untyped-def]
    r = _upload(client_a, "inv.pdf", pdf_bytes)
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["mime"] == "application/pdf" and body["page_count"] == 1
    assert body["duplicate_of"] is None
    doc = Document.objects.get(pk=body["id"])
    assert doc.file in fake_storage
    # eager Celery ran the (stub) extraction on commit; in tests on_commit fires immediately? no —
    # pytest-django wraps in a transaction so on_commit never fires. Status stays pending.
    assert doc.status == DocumentStatus.PENDING


def test_duplicate_upload_returns_200_with_duplicate_of(client_a, pdf_bytes) -> None:  # type: ignore[no-untyped-def]
    first = _upload(client_a, "a.pdf", pdf_bytes).json()
    r = _upload(client_a, "b.pdf", pdf_bytes)
    assert r.status_code == 200
    assert r.json()["duplicate_of"] == first["id"]
    assert Document.objects.count() == 1


def test_same_file_in_another_org_is_not_a_duplicate(client_a, client_b, pdf_bytes) -> None:  # type: ignore[no-untyped-def]
    assert _upload(client_a, "a.pdf", pdf_bytes).status_code == 201
    assert _upload(client_b, "a.pdf", pdf_bytes).status_code == 201


def test_exe_disguised_as_pdf_rejected(client_a) -> None:  # type: ignore[no-untyped-def]
    r = _upload(client_a, "invoice.pdf", b"MZ\x90\x00" + b"\x00" * 100)
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]
    assert Document.objects.count() == 0


def test_oversize_rejected(org_a) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(UploadError, match="25 MB"):
        ingest_bytes(org_a.org, data=b"%PDF" + b"0" * MAX_BYTES, filename="big.pdf")


def test_png_and_jpeg_accepted(client_a) -> None:  # type: ignore[no-untyped-def]
    assert (
        _upload(client_a, "a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png").status_code == 201
    )
    assert (
        _upload(client_a, "b.jpg", b"\xff\xd8\xff\xe0" + b"0" * 20, "image/jpeg").status_code == 201
    )


def test_bulk_zip_expands(client_a, pdf_bytes) -> None:  # type: ignore[no-untyped-def]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("one.pdf", pdf_bytes)
        zf.writestr("two.pdf", pdf_bytes + b"\n%x")
        zf.writestr("junk.txt", b"hello")
    r = client_a.post(
        "/api/documents/bulk/", {"files": [SimpleUploadedFile("batch.zip", buf.getvalue())]}
    )
    assert r.status_code == 207
    results = r.json()["results"]
    assert [x.get("original_filename") for x in results] == ["one.pdf", "two.pdf", "junk.txt"]
    assert "error" in results[2]
    assert Document.objects.count() == 2


def test_signed_url_expires_in_five_minutes(client_a, org_a, settings) -> None:  # type: ignore[no-untyped-def]
    settings.AWS_S3_ENDPOINT_URL = "http://minio:9000"
    doc = DocumentFactory(org=org_a.org)
    r = client_a.get(f"/api/documents/{doc.id}/file/")
    assert r.status_code == 200
    assert r.json()["expires_in"] == 300
    qs = parse_qs(urlparse(r.json()["url"]).query)
    assert qs["X-Amz-Expires"] == ["300"]
    assert storage.signed_get_url(doc.file, ttl=1) != r.json()["url"]


def test_cross_org_document_is_404(client_a, org_b) -> None:  # type: ignore[no-untyped-def]
    doc = DocumentFactory(org=org_b.org)
    assert client_a.get(f"/api/documents/{doc.id}/").status_code == 404
    assert client_a.get(f"/api/documents/{doc.id}/file/").status_code == 404


def test_task_is_idempotent(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from apps.documents import tasks

    monkeypatch.setattr(tasks, "run_extraction", lambda d: None)
    doc = DocumentFactory(org=org_a.org)
    assert extract_document.apply(args=[str(doc.pk)]).get() == "extracted"
    assert extract_document.apply(args=[str(doc.pk)]).get() == "skipped:extracted"
    doc.refresh_from_db()
    assert doc.attempts == 1


def test_task_records_failure_reason_after_max_attempts(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from apps.documents import tasks

    def boom(document: Document) -> None:
        raise RuntimeError("model said no")

    monkeypatch.setattr(tasks, "run_extraction", boom)
    doc = DocumentFactory(org=org_a.org, attempts=tasks.MAX_ATTEMPTS - 1)
    assert extract_document.apply(args=[str(doc.pk)]).get() == "failed"
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.FAILED
    assert "model said no" in doc.error


def test_task_retry_config() -> None:
    assert extract_document.max_retries == 2  # 3 attempts total
    assert extract_document.retry_backoff is True


def test_missing_document_is_noop() -> None:
    import uuid

    assert extract_document.apply(args=[str(uuid.uuid4())]).get() == "missing"
