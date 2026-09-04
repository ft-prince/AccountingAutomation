"""Celery entry points. Idempotent; take IDs, not objects."""

import logging

from celery import shared_task
from django.conf import settings

from apps.documents.models import Document, DocumentStatus
from apps.documents.services import mark_failed

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 6  # paced by EXTRACTION_RATE_LIMIT, so retries mostly wait rather than fail


def run_extraction(document: Document) -> str:
    """PROJECT_SPECS §5: model call → validated ExtractionRun → invoice ingest.
    Returns the document status to record: EXTRACTED, or NOT_INVOICE when the model read the
    file as a letter, report, quote, PO, receipt or note — then nothing is booked."""
    from apps.documents.services.extraction import extract
    from apps.documents.services.schema import INVOICE_KINDS
    from apps.invoices.services import ingest_extraction

    run = extract(document)
    kind = (run.parsed or {}).get("document_kind", "tax_invoice")
    if kind not in INVOICE_KINDS:
        document.error = f"Not an invoice: the model read this as '{kind}'. Nothing was booked."
        document.save(update_fields=["error", "updated_at"])
        return DocumentStatus.NOT_INVOICE
    ingest_extraction(run)
    return DocumentStatus.EXTRACTED


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=MAX_ATTEMPTS - 1,
    rate_limit=settings.EXTRACTION_RATE_LIMIT,
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
        doc.status = run_extraction(doc) or DocumentStatus.EXTRACTED
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
