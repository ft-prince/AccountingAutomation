"""Intent classification with Claude tool-use. PROJECT_SPECS §6.4 — deterministic labels."""

from typing import Any

from django.conf import settings
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticError

from apps.mail.domain.sla import sla_due
from apps.mail.models import (
    EmailMessage,
    EmailThread,
    Intent,
    MessageDirection,
    Priority,
    Sentiment,
    ThreadStatus,
)
from apps.mail.services import llm
from apps.mail.services.party_resolution import apply_resolution

PROMPT_VERSION = "classify_email_v1"
TOOL_NAME = "classify_email"
MAX_BODY_CHARS = 12000

CLASSIFY_TOOL: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": "Record the intent, priority and sentiment of one inbound business email.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": list(Intent.values)},
            "priority": {"type": "string", "enum": list(Priority.values)},
            "sentiment": {"type": "string", "enum": list(Sentiment.values)},
            "requires_finance_data": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["intent", "priority", "sentiment", "requires_finance_data", "reason"],
        "additionalProperties": False,
    },
}


class Classification(BaseModel):
    intent: Intent
    priority: Priority
    sentiment: Sentiment
    requires_finance_data: bool
    reason: str = Field(default="", max_length=2000)


class ClassificationError(Exception):
    pass


def wrap_untrusted(message: EmailMessage) -> str:
    """CLAUDE.md §4: the email is DATA. Delimit it so the model treats it that way."""
    body = message.body_text[:MAX_BODY_CHARS]
    return (
        "<untrusted_email>\n"
        f"From: {message.from_address}\n"
        f"To: {', '.join(message.to_addresses)}\n"
        f"Date: {message.date.isoformat()}\n"
        f"Subject: {message.subject}\n\n"
        f"{body}\n"
        "</untrusted_email>"
    )


def latest_inbound(thread: EmailThread) -> EmailMessage | None:
    return (
        EmailMessage.objects.filter(thread=thread, direction=MessageDirection.INBOUND)
        .order_by("-date")
        .first()
    )


def classify_message(message: EmailMessage, *, client: Any | None = None) -> Classification:
    reply = llm.call_tool(
        client or llm.client(),
        system=llm.prompt_text(PROMPT_VERSION),
        messages=[{"role": "user", "content": wrap_untrusted(message)}],
        tool=CLASSIFY_TOOL,
    )
    try:
        return Classification.model_validate(llm.require_tool_input(reply, TOOL_NAME))
    except (PydanticError, llm.LLMError) as exc:
        raise ClassificationError(str(exc)) from exc


def classify_thread(thread: EmailThread, *, client: Any | None = None) -> EmailThread:
    """Classify the latest inbound message, resolve the party, recompute the SLA."""
    message = latest_inbound(thread)
    if message is None:
        raise ClassificationError("thread has no inbound message")
    result = classify_message(message, client=client)
    thread.intent = result.intent
    thread.priority = result.priority
    thread.sentiment = result.sentiment
    thread.requires_finance_data = result.requires_finance_data
    thread.classification_prompt_version = PROMPT_VERSION
    thread.classification_model = settings.ANTHROPIC_MODEL
    if thread.last_inbound_at is not None:
        thread.sla_due_at = sla_due(thread.last_inbound_at, thread.priority)
    if thread.status == ThreadStatus.NEW and result.intent != Intent.NEWSLETTER_OR_SPAM:
        thread.status = ThreadStatus.AWAITING_REVIEW
    thread.save()
    apply_resolution(
        thread, sender=message.from_address, text=f"{message.subject}\n{message.body_text}"
    )
    return thread
