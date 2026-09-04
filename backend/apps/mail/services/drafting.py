"""Draft generation. PROJECT_SPECS §6.5: retrieve context → tool-use → OUR guardrail pass →
EmailDraft(pending_review). The model never sends; a human reviews (§6.1)."""

import html
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticError

from apps.core.audit import record
from apps.mail.domain import guardrails
from apps.mail.models import DraftStatus, EmailDraft, EmailThread, ThreadStatus
from apps.mail.services import llm
from apps.mail.services.classification import latest_inbound
from apps.mail.services.context import build_snapshot

PROMPT_VERSION = "draft_reply_v1"
TOOL_NAME = "draft_reply"
TONES = ("formal", "friendly", "firm", "apologetic")
SUPERSEDABLE = (DraftStatus.PENDING_REVIEW, DraftStatus.APPROVED, DraftStatus.EDITED_APPROVED)

DRAFT_TOOL: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": "Record the drafted reply for human review.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "body_text": {"type": "string"},
            "tone": {"type": "string", "enum": list(TONES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "self_reported_flags": {
                "type": "array",
                "items": {"type": "string", "enum": list(guardrails.ALL_FLAGS)},
            },
        },
        "required": ["body_text", "tone", "confidence", "self_reported_flags"],
        "additionalProperties": False,
    },
}


class DraftReply(BaseModel):
    body_text: str = Field(min_length=1, max_length=20000)
    tone: str = Field(max_length=30)
    confidence: Decimal = Field(ge=0, le=1)
    self_reported_flags: list[str] = Field(default_factory=list, max_length=20)


class DraftError(Exception):
    pass


def snapshot_for_guardrails(
    snapshot: dict[str, Any], self_reported: list[str]
) -> guardrails.Snapshot:
    allowed = snapshot.get("allowed", {})
    return guardrails.Snapshot(
        amounts=frozenset(allowed.get("amounts", [])),
        invoice_numbers=frozenset(allowed.get("invoice_numbers", [])),
        dates=frozenset(allowed.get("dates", [])),
        party_resolved=bool(snapshot.get("party_resolved")),
        inbound_sentiment=str(snapshot.get("inbound_sentiment") or ""),
        inbound_injection_flag=bool(snapshot.get("inbound_injection_flag")),
        self_reported_flags=tuple(self_reported),
    )


def text_to_html(text: str) -> str:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)


def call_model(client: Any, snapshot: dict[str, Any]) -> DraftReply:
    request = snapshot["llm_request"]
    reply = llm.call_tool(
        client, system=request["system"], messages=request["messages"], tool=DRAFT_TOOL
    )
    try:
        return DraftReply.model_validate(llm.require_tool_input(reply, TOOL_NAME))
    except (PydanticError, llm.LLMError) as exc:
        raise DraftError(str(exc)) from exc


def generate_draft(
    thread: EmailThread,
    *,
    actor: Any = None,
    instruction: str | None = None,
    client: Any | None = None,
) -> EmailDraft:
    """New version; any prior live draft on the thread becomes superseded."""
    inbound = latest_inbound(thread)
    if inbound is None:
        raise DraftError("thread has no inbound message to reply to")
    snapshot = build_snapshot(
        thread,
        inbound,
        system_prompt=llm.prompt_text(PROMPT_VERSION),
        instruction=instruction,
        today=timezone.localdate(),
    )
    reply = call_model(client or llm.client(), snapshot)
    flags = guardrails.check(
        reply.body_text, snapshot_for_guardrails(snapshot, reply.self_reported_flags)
    )
    with transaction.atomic():
        EmailDraft.objects.filter(thread=thread, status__in=SUPERSEDABLE).update(
            status=DraftStatus.SUPERSEDED, updated_at=timezone.now()
        )
        version = (
            EmailDraft.objects.filter(thread=thread).aggregate(m=Max("version"))["m"] or 0
        ) + 1
        draft = EmailDraft.objects.create(
            org=thread.org,
            thread=thread,
            in_reply_to=inbound,
            version=version,
            prompt_version=PROMPT_VERSION,
            model_name=settings.ANTHROPIC_MODEL,
            context_snapshot=snapshot,
            body_text=reply.body_text,
            body_html=text_to_html(reply.body_text),
            tone=reply.tone,
            confidence=reply.confidence.quantize(Decimal("0.001")),
            guardrail_flags=flags,
            instruction=instruction or "",
            created_by=actor if getattr(actor, "pk", None) else None,
        )
        thread.status = ThreadStatus.DRAFTED
        thread.save(update_fields=["status", "updated_at"])
        record(
            thread.org,
            actor=actor,
            entity=draft,
            action="draft.generate",
            after={"version": version, "flags": flags, "instruction": instruction},
        )
    return draft
