"""Pure renderers for scheduled reports: XLSX bytes and a minimal text PDF. No I/O, no Django."""

import io
from typing import Any


def _rows(payload: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    """Flatten a report payload: prefer its `rows`, else key/value pairs. Values are strings."""
    rows = payload.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        header = list(rows[0].keys())
        return header, [[str(r.get(h, "")) for h in header] for r in rows]
    header = ["field", "value"]
    return header, [
        [k, str(v)] for k, v in payload.items() if k != "meta" and not isinstance(v, dict | list)
    ]


def render_xlsx(name: str, payload: dict[str, Any]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = name[:31]
    meta = payload.get("meta", {})
    ws.append(
        [
            f"{name} · FY {meta.get('fy', '')} · {meta.get('basis', '')}"
            f" · pending {meta.get('pending_count', 0)}"
        ]
    )
    header, body = _rows(payload)
    ws.append(header)
    for r in body:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_pdf(name: str, payload: dict[str, Any]) -> bytes:
    """Text-only PDF (Helvetica), one page per 60 lines. Fixed content, no model text."""
    meta = payload.get("meta", {})
    header, body = _rows(payload)
    lines = [
        f"{name}  FY {meta.get('fy', '')}  {meta.get('basis', '')}"
        f"  pending {meta.get('pending_count', 0)}",
        " | ".join(header),
    ]
    lines += [" | ".join(r) for r in body]
    pages = [lines[i : i + 60] for i in range(0, len(lines), 60)] or [[]]
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]  # pages placeholder
    font_obj = 3
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    for page in pages:
        content = (
            "BT /F1 9 Tf 36 800 Td 11 TL "
            + " ".join(f"({_esc(ln[:120])}) Tj T*" for ln in page)
            + " ET"
        ).encode("latin-1", "replace")
        objs.append(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
        content_id = len(objs)
        objs.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents "
            + str(content_id).encode()
            + b" 0 R /Resources << /Font << /F1 "
            + str(font_obj).encode()
            + b" 0 R >> >> >>"
        )
        page_ids.append(len(objs))
    objs[1] = (
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{i} 0 R".encode() for i in page_ids)
        + b"] /Count "
        + str(len(page_ids)).encode()
        + b" >>"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
