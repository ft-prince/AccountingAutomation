"""Anthropic extraction pipeline. PROJECT_SPECS §5.
PDF in → tool-use call → Pydantic → gst.domain validators → ExtractionRun (append-only)."""

import base64
import io
import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import anthropic
import pdfplumber
from django.conf import settings
from pydantic import ValidationError as PydanticError

from apps.documents import storage
from apps.documents.models import Document, ExtractionRun
from apps.documents.services.schema import INVOICE_TOOL, ExtractedInvoice

log = logging.getLogger(__name__)

PROMPT_VERSION = "extract_invoice_v1"
PROMPT_PATH = Path(settings.BASE_DIR) / "prompts" / f"{PROMPT_VERSION}.txt"
SCAN_CHARS_PER_PAGE = 50  # §5: below this the PDF has no usable text layer
MAX_TOKENS = 16000


class ExtractionError(Exception):
    pass


class SchemaError(ExtractionError):
    pass


@dataclass(frozen=True)
class ModelReply:
    tool_input: dict[str, Any] | None
    raw: dict[str, Any]
    input_tokens: int
    output_tokens: int
    stop_reason: str


def _client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise ExtractionError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=3)


def has_text_layer(pdf_bytes: bytes) -> bool:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages
        if not pages:
            return False
        chars = sum(len(p.extract_text() or "") for p in pages)
        return chars / len(pages) >= SCAN_CHARS_PER_PAGE


def render_pages(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    out: list[bytes] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            buf = io.BytesIO()
            page.to_image(resolution=dpi).original.save(buf, format="PNG")
            out.append(buf.getvalue())
    return out


def build_content(data: bytes, mime: str) -> list[dict[str, Any]]:
    """Text-layer PDF → document block; scanned PDF → page images; image → image block."""
    if mime == "application/pdf":
        if has_text_layer(data):
            return [_document_block(data)]
        return [_image_block(png, "image/png") for png in render_pages(data)]
    return [_image_block(data, mime)]


def _document_block(pdf: bytes) -> dict[str, Any]:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(pdf).decode(),
        },
    }


def _image_block(img: bytes, mime: str) -> dict[str, Any]:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": mime,
            "data": base64.standard_b64encode(img).decode(),
        },
    }


def call_model(
    client: Any, content: list[dict[str, Any]], *, feedback: str | None = None
) -> ModelReply:
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": [*content, {"type": "text", "text": "Extract this invoice."}]}
    ]
    if feedback:
        messages[0]["content"].append(
            {
                "type": "text",
                "text": f"A previous attempt failed validation: {feedback}. Try again.",
            }
        )
    resp = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=PROMPT_PATH.read_text(),
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": INVOICE_TOOL["name"]},
        messages=messages,
    )
    tool_input = next((b.input for b in resp.content if b.type == "tool_use"), None)
    raw = resp.to_dict() if hasattr(resp, "to_dict") else {"content": str(resp.content)}
    return ModelReply(
        tool_input=tool_input,
        raw=raw,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        stop_reason=resp.stop_reason or "",
    )


def parse_reply(reply: ModelReply) -> ExtractedInvoice:
    if reply.stop_reason == "refusal":
        raise ExtractionError("model refused the request")
    if reply.tool_input is None:
        raise SchemaError("model did not call record_invoice")
    try:
        return ExtractedInvoice.model_validate(reply.tool_input)
    except PydanticError as exc:
        raise SchemaError(str(exc)) from exc


def cost_inr(input_tokens: int, output_tokens: int) -> Decimal:
    p = settings.ANTHROPIC_PRICE_USD_PER_MTOK
    usd = (Decimal(input_tokens) * p["input"] + Decimal(output_tokens) * p["output"]) / Decimal(
        1_000_000
    )
    return (usd * settings.USD_INR_RATE).quantize(Decimal("0.0001"))


def extract(document: Document, *, client: Any | None = None) -> ExtractionRun:
    """Run the pipeline once, appending an ExtractionRun. Raises on failure after recording it."""
    client = client or _client()
    started = time.monotonic()
    data = storage.get_object(document.file)
    content = build_content(data, document.mime)
    tokens_in = tokens_out = 0
    raw: dict[str, Any] = {}
    try:
        reply = call_model(client, content)
        tokens_in, tokens_out, raw = reply.input_tokens, reply.output_tokens, reply.raw
        try:
            parsed = parse_reply(reply)
        except SchemaError as first:
            # §5: on schema failure retry ONCE with the error fed back, then fail.
            reply = call_model(client, content, feedback=str(first)[:1500])
            tokens_in += reply.input_tokens
            tokens_out += reply.output_tokens
            raw = {"first_attempt": raw, "retry": reply.raw}
            parsed = parse_reply(reply)
    except Exception as exc:
        run = ExtractionRun.objects.create(
            document=document,
            model_name=settings.ANTHROPIC_MODEL,
            prompt_version=PROMPT_VERSION,
            raw_response=raw or None,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cost_inr=cost_inr(tokens_in, tokens_out),
            latency_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}"[:2000],
        )
        raise ExtractionError(run.error) from exc

    issues = validate_extracted(parsed, document)
    return ExtractionRun.objects.create(
        document=document,
        model_name=settings.ANTHROPIC_MODEL,
        prompt_version=PROMPT_VERSION,
        raw_response=raw,
        parsed=parsed.dump(),
        field_confidence=parsed.field_confidence,
        validation_issues=issues,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_inr=cost_inr(tokens_in, tokens_out),
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def validate_extracted(parsed: ExtractedInvoice, document: Document) -> list[dict[str, Any]]:
    """Bridge Pydantic output → apps.gst.domain.validators. JSON-safe issue dicts."""
    from apps.documents.services.validation import run_domain_validation

    return [i.__dict__ | {"severity": str(i.severity)} for i in run_domain_validation(parsed)]


def load_expected(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
