"""Shared Anthropic tool-use call for classification and drafting. The API key is read from
settings at call time and is never logged or stored."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
from django.conf import settings

MAX_TOKENS = 4000
PROMPTS_DIR = Path(settings.BASE_DIR) / "prompts"


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class ToolReply:
    tool_input: dict[str, Any] | None
    stop_reason: str
    input_tokens: int
    output_tokens: int


def client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=3)


def prompt_text(prompt_version: str) -> str:
    return (PROMPTS_DIR / f"{prompt_version}.txt").read_text()


def call_tool(
    llm: Any, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any]
) -> ToolReply:
    resp = llm.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=messages,
    )
    tool_input = next((b.input for b in resp.content if b.type == "tool_use"), None)
    return ToolReply(
        tool_input=tool_input,
        stop_reason=resp.stop_reason or "",
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


def require_tool_input(reply: ToolReply, tool_name: str) -> dict[str, Any]:
    if reply.stop_reason == "refusal":
        raise LLMError("model refused the request")
    if reply.tool_input is None:
        raise LLMError(f"model did not call {tool_name}")
    return reply.tool_input
