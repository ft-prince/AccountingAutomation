"""Document organisation export. PROJECT_SPECS Phase 19: originals renamed
{invoice_date}_{party_slug}_{invoice_number}.pdf, foldered FY/month, collision-suffixed,
streamed. Originals are never modified."""

import re
import zipfile
from collections.abc import Iterator
from datetime import date
from io import BytesIO
from typing import Any

from django.utils.text import slugify

from apps.documents import storage
from apps.invoices.models import Invoice, InvoiceStatus

_UNSAFE = re.compile(r"[^A-Za-z0-9-]+")
EXT = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}


def safe_name(invoice_date: date, party: str, number: str, mime: str) -> str:
    num = _UNSAFE.sub("-", number).strip("-") or "no-number"
    return (
        f"{invoice_date.isoformat()}_{slugify(party)[:40] or 'party'}_{num}.{EXT.get(mime, 'bin')}"
    )


def folder_for(invoice: Invoice) -> str:
    return f"FY{invoice.fy}/{invoice.period_month}"


def iter_documents(
    org: Any, *, period: str | None = None, fy: str | None = None
) -> Iterator[tuple[str, Invoice]]:
    qs = (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED, document__isnull=False)
        .select_related("document", "party")
        .order_by("invoice_date", "invoice_number")
    )
    if period:
        qs = qs.filter(period_month=period)
    if fy:
        qs = qs.filter(fy=fy)
    seen: dict[str, int] = {}
    for inv in qs:
        name = safe_name(
            inv.invoice_date, inv.party.legal_name, inv.invoice_number, inv.document.mime
        )
        base = f"{folder_for(inv)}/{name}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        if n:
            stem, ext = base.rsplit(".", 1)
            base = f"{stem}_{n + 1}.{ext}"
        yield base, inv


def build_zip(org: Any, *, period: str | None = None, fy: str | None = None) -> Iterator[bytes]:
    """Stream a zip: one member per confirmed invoice document. Memory stays flat per file."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for name, inv in iter_documents(org, period=period, fy=fy):
            assert inv.document is not None
            zf.writestr(name, storage.get_object(inv.document.file))
            count += 1
            if buf.tell() > 8 * 1024 * 1024:  # flush chunk to the client, keep going
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        zf.writestr(
            "README.txt",
            f"Nexren Finance document export\nConfirmed invoices: {count}\n"
            "Originals are unmodified copies.\n",
        )
    yield buf.getvalue()
