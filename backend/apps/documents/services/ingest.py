"""Upload → sha256 dedupe → Document(pending) → queue extraction. PROJECT_SPECS §5."""

import hashlib
import io
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from pypdf import PdfReader

from apps.documents import storage
from apps.documents.models import Document, DocumentSource, DocumentStatus

MAX_BYTES = 25 * 1024 * 1024
MAGIC: dict[bytes, str] = {
    b"%PDF": "application/pdf",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


class UploadError(ValueError):
    pass


def sniff_mime(data: bytes) -> str:
    for magic, mime in MAGIC.items():
        if data.startswith(magic):
            return mime
    raise UploadError("Unsupported file type: only PDF, PNG and JPEG are accepted.")


def _page_count(data: bytes, mime: str) -> int | None:
    if mime != "application/pdf":
        return 1
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:  # noqa: BLE001 — malformed PDF: still store, page_count unknown
        return None


@dataclass(frozen=True)
class IngestResult:
    document: Document
    duplicate_of: Document | None


def ingest_bytes(
    org: Any,
    *,
    data: bytes,
    filename: str,
    uploaded_by: Any = None,
    source: str = DocumentSource.UPLOAD,
) -> IngestResult:
    if len(data) > MAX_BYTES:
        raise UploadError("File exceeds the 25 MB limit.")
    if not data:
        raise UploadError("Empty file.")
    mime = sniff_mime(data)
    digest = hashlib.sha256(data).hexdigest()
    existing = Document.objects.for_org(org).filter(sha256=digest).first()
    if existing:
        return IngestResult(document=existing, duplicate_of=existing)

    key = f"org/{org.pk}/documents/{uuid.uuid4()}"
    storage.put_object(key, data, mime)
    try:
        with transaction.atomic():
            doc = Document.objects.create(
                org=org,
                file=key,
                sha256=digest,
                original_filename=filename[:255],
                mime=mime,
                size_bytes=len(data),
                page_count=_page_count(data, mime),
                source=source,
                uploaded_by=uploaded_by if getattr(uploaded_by, "pk", None) else None,
            )
    except IntegrityError:  # raced with a concurrent identical upload
        existing = Document.objects.for_org(org).get(sha256=digest)
        return IngestResult(document=existing, duplicate_of=existing)

    from apps.documents.tasks import extract_document

    transaction.on_commit(lambda: extract_document.delay(str(doc.pk)))
    return IngestResult(document=doc, duplicate_of=None)


def expand_zip(data: bytes) -> list[tuple[str, bytes]]:
    """Return (name, bytes) for supported files inside a zip; skips directories and junk."""
    out: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX"):
                continue
            if info.file_size > MAX_BYTES:
                continue
            out.append((info.filename.rsplit("/", 1)[-1], zf.read(info)))
    return out


def mark_failed(document: Document, reason: str) -> None:
    document.status = DocumentStatus.FAILED
    document.error = reason[:2000]
    document.save(update_fields=["status", "error", "updated_at"])
