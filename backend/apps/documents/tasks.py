"""Celery entry points. Idempotent; take IDs, not objects."""

import logging

from celery import shared_task

from apps.documents.models import Document, DocumentStatus
from apps.documents.services import mark_failed

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def run_extraction(document: Document) -> None:
    """PROJECT_SPECS §5: model call → validated ExtractionRun → (Phase 7) invoice ingest."""
    from apps.documents.services.extraction import extract

    run = extract(document)
    ingest = getattr(run, "ingest_hook", None)  # Phase 7 registers apps.invoices.services.ingest
    if ingest:
        ingest(run)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=MAX_ATTEMPTS - 1,
)
def extract_document(self, document_id: str) -> str:  # type: ignore[no-untyped-def]
    doc = Document.objects.filter(pk=document_id).first()
    if doc is None:
        return "missing"
    if doc.status not in (DocumentStatus.PENDING, DocumentStatus.EXTRACTING):
        return f"skipped:{doc.status}"  # idempotent: already extracted / failed / superseded
    doc.status = DocumentStatus.EXTRACTING
    doc.attempts += 1
    doc.save(update_fields=["status", "attempts", "updated_at"])
    try:
        run_extraction(doc)
        doc.status = DocumentStatus.EXTRACTED
        doc.save(update_fields=["status", "updated_at"])
    except Exception as exc:
        log.exception("extract_document failed", extra={"document_id": document_id})
        if doc.attempts >= MAX_ATTEMPTS:
            mark_failed(doc, f"{type(exc).__name__}: {exc}")
            return "failed"
        doc.status = DocumentStatus.PENDING
        doc.save(update_fields=["status", "updated_at"])
        raise
    return "extracted"
