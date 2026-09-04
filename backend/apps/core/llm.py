"""Provider-neutral LLM tool-use entry point (PROJECT_SPECS §5, §6.4, §8.8).

One function — `call_tool` — backed either by the Anthropic SDK or by Groq's
OpenAI-compatible `/chat/completions` endpoint. Call sites always describe the tool
in the ANTHROPIC shape ({"name", "description", "strict", "input_schema"}); the Groq
adapter translates it to {"type": "function", "function": {...}}.

Model output stays untrusted (CLAUDE.md §4): this module only transports and parses,
it never decides that a result is valid. The API key is read from settings at call
time and is never logged, echoed, or placed in an exception message.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx2 as httpx
from django.conf import settings

log = logging.getLogger(__name__)

ANTHROPIC = "anthropic"
GROQ = "groq"
PROVIDERS = (ANTHROPIC, GROQ)

DEFAULT_MAX_TOKENS = 4000
TIMEOUT_SECONDS = 60.0
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 30.0
BODY_EXCERPT_CHARS = 400
REDACTED = "***"


class LLMError(Exception):
    """The call could not be completed, or the provider refused it."""


class SchemaError(LLMError):
    """The model did not return usable tool input."""


@dataclass(frozen=True)
class ToolReply:
    tool_input: dict[str, Any] | None
    stop_reason: str
    input_tokens: int
    output_tokens: int
    model: str


# --------------------------------------------------------------------------- provider selection


def active_provider(provider: str | None = None) -> str:
    name = (provider or getattr(settings, "LLM_PROVIDER", ANTHROPIC) or ANTHROPIC).strip().lower()
    if name not in PROVIDERS:
        raise LLMError(f"unknown LLM provider {name!r}; expected one of {', '.join(PROVIDERS)}")
    return name


def has_api_key(provider: str | None = None) -> bool:
    if active_provider(provider) == GROQ:
        return bool(settings.GROQ_API_KEY)
    return bool(settings.ANTHROPIC_API_KEY)


def configured_model(*, provider: str | None = None, has_images: bool = False) -> str:
    """The model this provider would use, or "" when it is not configured. Never raises."""
    if active_provider(provider) == GROQ:
        return settings.GROQ_VISION_MODEL if has_images else settings.GROQ_MODEL
    return settings.ANTHROPIC_MODEL


def build_client(provider: str | None = None) -> Any:
    """The transport a call site should reuse: the Anthropic SDK, or an HTTP client for Groq."""
    if active_provider(provider) == GROQ:
        if not settings.GROQ_API_KEY:
            raise LLMError("GROQ_API_KEY is not configured")
        return httpx.Client(timeout=TIMEOUT_SECONDS)
    return _anthropic_client()


# --------------------------------------------------------------------------- entry point


def call_tool(
    *,
    system: str,
    messages: list[dict[str, Any]],
    tool: dict[str, Any],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: Any | None = None,
    provider: str | None = None,
) -> ToolReply:
    """Force `tool` and return its parsed input. Raises SchemaError when none came back."""
    if active_provider(provider) == GROQ:
        return _call_groq(
            system=system, messages=messages, tool=tool, max_tokens=max_tokens, client=client
        )
    return _call_anthropic(
        system=system, messages=messages, tool=tool, max_tokens=max_tokens, client=client
    )


# --------------------------------------------------------------------------- anthropic


def _anthropic_client() -> Any:
    import anthropic

    if not settings.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=MAX_ATTEMPTS)


def _call_anthropic(
    *,
    system: str,
    messages: list[dict[str, Any]],
    tool: dict[str, Any],
    max_tokens: int,
    client: Any | None,
) -> ToolReply:
    llm = client if client is not None else _anthropic_client()
    resp = llm.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
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
        model=settings.ANTHROPIC_MODEL,
    )


# --------------------------------------------------------------------------- groq translation


def groq_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool shape → OpenAI function shape (Groq docs: tools[].function.parameters)."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def _groq_block(block: dict[str, Any]) -> dict[str, Any]:
    kind = block.get("type")
    if kind == "text":
        return {"type": "text", "text": block.get("text", "")}
    if kind == "image":
        return {"type": "image_url", "image_url": {"url": _data_uri(block)}}
    if kind == "document":
        raise LLMError(
            "Groq's chat completions API cannot accept PDF document blocks; "
            "send the PDF's extracted text or its page images instead"
        )
    raise LLMError(f"content block type {kind!r} cannot be sent to Groq")


def _data_uri(block: dict[str, Any]) -> str:
    source = block.get("source") or {}
    if source.get("type") != "base64":
        raise LLMError("Groq images must be supplied as base64 content blocks")
    return f"data:{source.get('media_type', '')};base64,{source.get('data', '')}"


def groq_messages(system: str, messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Returns (OpenAI messages with the system prompt first, whether any image is present)."""
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    has_images = False
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            out.append({"role": message.get("role", "user"), "content": content})
            continue
        blocks = [_groq_block(b) for b in content or []]
        has_images = has_images or any(b["type"] == "image_url" for b in blocks)
        out.append({"role": message.get("role", "user"), "content": blocks})
    return out, has_images


def _groq_model(has_images: bool) -> str:
    if not has_images:
        return settings.GROQ_MODEL
    if not settings.GROQ_VISION_MODEL:
        raise LLMError(
            "this document was sent as page images and GROQ_VISION_MODEL is not set; "
            "configure a Groq vision model to process scanned documents"
        )
    return settings.GROQ_VISION_MODEL


# --------------------------------------------------------------------------- groq call


def _call_groq(
    *,
    system: str,
    messages: list[dict[str, Any]],
    tool: dict[str, Any],
    max_tokens: int,
    client: Any | None,
) -> ToolReply:
    if not settings.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not configured")
    payload, model = _groq_payload(
        system=system, messages=messages, tool=tool, max_tokens=max_tokens
    )
    http = client if client is not None else httpx.Client(timeout=TIMEOUT_SECONDS)
    response = _post_with_retries(http, payload)
    return _parse_groq(response, tool_name=tool["name"], model=model)


def _groq_payload(
    *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int
) -> tuple[dict[str, Any], str]:
    translated, has_images = groq_messages(system, messages)
    model = _groq_model(has_images)
    payload: dict[str, Any] = {
        "model": model,
        "messages": translated,
        "tools": [groq_tool(tool)],
        "tool_choice": {"type": "function", "function": {"name": tool["name"]}},
        "max_completion_tokens": max_tokens,
    }
    return payload, model


def _post_with_retries(http: Any, payload: dict[str, Any]) -> Any:
    url = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = http.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            reason = f"{type(exc).__name__}: {redact(str(exc))}"
            if attempt == MAX_ATTEMPTS:
                raise LLMError(_failed(attempt, reason)) from exc
            _sleep(_backoff(attempt, None))
            continue
        if response.status_code < 400:
            return response
        reason = f"HTTP {response.status_code} {redact(_body_excerpt(response))}"
        if _is_retryable(response.status_code) and attempt < MAX_ATTEMPTS:
            _sleep(_backoff(attempt, _retry_after(response)))
            continue
        raise LLMError(_failed(attempt, reason))
    raise LLMError(_failed(MAX_ATTEMPTS, "no response"))  # pragma: no cover - loop always exits


def _parse_groq(response: Any, *, tool_name: str, model: str) -> ToolReply:
    try:
        body = response.json()
    except Exception as exc:  # provider returned something that is not JSON
        raise SchemaError("Groq response was not JSON") from exc
    choices = body.get("choices") or []
    if not choices:
        raise SchemaError("Groq response contained no choices")
    message = choices[0].get("message") or {}
    calls = message.get("tool_calls") or []
    if not calls:
        raise SchemaError(f"model did not call {tool_name}")
    arguments = (calls[0].get("function") or {}).get("arguments")
    tool_input = _load_arguments(arguments, tool_name)
    usage = body.get("usage") or {}
    return ToolReply(
        tool_input=tool_input,
        stop_reason=str(choices[0].get("finish_reason") or ""),
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        model=str(body.get("model") or model),
    )


def _load_arguments(arguments: Any, tool_name: str) -> dict[str, Any]:
    """`function.arguments` is a JSON *string* on the OpenAI wire format."""
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        raise SchemaError(f"{tool_name} arguments were {type(arguments).__name__}, not a string")
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{tool_name} arguments were not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SchemaError(f"{tool_name} arguments were not a JSON object")
    return parsed


# --------------------------------------------------------------------------- retry helpers


def _is_retryable(status: int) -> bool:
    return status == 429 or status >= 500


def _retry_after(response: Any) -> float | None:
    raw = (getattr(response, "headers", None) or {}).get("retry-after")
    if not isinstance(raw, str | int | float):
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:  # the HTTP-date form of Retry-After — fall back to plain backoff
        return None


def _backoff(attempt: int, retry_after: float | None) -> float:
    wait = retry_after if retry_after is not None else BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    return min(wait, BACKOFF_MAX_SECONDS)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _failed(attempts: int, reason: str) -> str:
    hint = ""
    if "Request too large" in reason:
        hint = (
            " — the image or prompt exceeds this model's per-request token cap on your tier. "
            "Route scans elsewhere with EXTRACTION_SCAN_PROVIDER, or move to a paid tier."
        )
    return f"Groq request failed after {attempts} attempt(s): {reason}{hint}"


def _body_excerpt(response: Any) -> str:
    try:
        return str(response.text)[:BODY_EXCERPT_CHARS]
    except Exception:  # pragma: no cover - defensive; body is best-effort context only
        return ""


def redact(text: str) -> str:
    """Strip any configured API key out of text before it reaches a log or an exception."""
    for secret in (settings.GROQ_API_KEY, settings.ANTHROPIC_API_KEY):
        if secret:
            text = text.replace(secret, REDACTED)
    return text
