"""Shared tool-use call for classification and drafting, delegating to the provider-neutral
apps.core.llm. The API key is read from settings at call time and is never logged or stored."""

from pathlib import Path
from typing import Any

from django.conf import settings

from apps.core import llm as core_llm

MAX_TOKENS = core_llm.DEFAULT_MAX_TOKENS
PROMPTS_DIR = Path(settings.BASE_DIR) / "prompts"

# Re-exported so callers (views, classification, drafting) keep one error type and one shape.
LLMError = core_llm.LLMError
SchemaError = core_llm.SchemaError
ToolReply = core_llm.ToolReply


def client() -> Any:
    """The provider transport for this org's configured LLM_PROVIDER."""
    return core_llm.build_client()


def prompt_text(prompt_version: str) -> str:
    return (PROMPTS_DIR / f"{prompt_version}.txt").read_text()


def call_tool(
    llm: Any, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any]
) -> ToolReply:
    return core_llm.call_tool(
        system=system, messages=messages, tool=tool, max_tokens=MAX_TOKENS, client=llm
    )


def require_tool_input(reply: ToolReply, tool_name: str) -> dict[str, Any]:
    if reply.stop_reason == "refusal":
        raise LLMError("model refused the request")
    if reply.tool_input is None:
        raise LLMError(f"model did not call {tool_name}")
    return reply.tool_input
