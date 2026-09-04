"""apps.core.llm — provider-neutral tool-use. No network: every HTTP call is a fake client."""

import json
import logging
from typing import Any

import pytest

from apps.core import llm as core_llm
from apps.core.llm import LLMError, SchemaError, call_tool
from apps.documents.tests.fakes import FakeAnthropic

TOOL: dict[str, Any] = {
    "name": "record_thing",
    "description": "Record one thing.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": False,
    },
}
SYSTEM = "You are a careful extractor."
TEXT_MESSAGES: list[dict[str, Any]] = [{"role": "user", "content": "hello"}]


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.text = text if text is not None else json.dumps(body or {})

    def json(self) -> dict[str, Any]:
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakeHTTP:
    """Stands in for httpx2.Client: records requests, replays canned responses."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> Any:
        self.requests.append({"url": url, **kwargs})
        reply = self._responses.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def ok_body(
    arguments: Any = '{"a": "one"}',
    *,
    tool_calls: bool = True,
    model: str = "llama-3.3-70b-versatile",
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": None}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": TOOL["name"], "arguments": arguments},
            }
        ]
    return {
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 300, "total_tokens": 1500},
    }


@pytest.fixture
def groq(settings) -> None:  # type: ignore[no-untyped-def]
    settings.LLM_PROVIDER = "groq"
    settings.GROQ_API_KEY = "gsk-TEST-SECRET"
    settings.GROQ_BASE_URL = "https://api.groq.com/openai/v1"
    settings.GROQ_MODEL = "llama-3.3-70b-versatile"
    settings.GROQ_VISION_MODEL = ""


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch) -> list[float]:  # type: ignore[no-untyped-def]
    waits: list[float] = []
    monkeypatch.setattr(core_llm, "_sleep", waits.append)
    return waits


def _image_message(media_type: str = "image/png") -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": "QUJD"},
                },
                {"type": "text", "text": "Extract this."},
            ],
        }
    ]


# --------------------------------------------------------------------------- request translation


def test_groq_request_translates_tool_forces_it_and_puts_system_first(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=ok_body())])

    call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, max_tokens=777, client=http)

    sent = http.requests[0]
    assert sent["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer gsk-TEST-SECRET"
    assert sent["timeout"] == core_llm.TIMEOUT_SECONDS
    payload = sent["json"]
    assert payload["model"] == "llama-3.3-70b-versatile"
    assert payload["max_completion_tokens"] == 777
    assert payload["messages"][0] == {"role": "system", "content": SYSTEM}
    assert payload["messages"][1] == {"role": "user", "content": "hello"}
    assert payload["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "record_thing",
                "description": "Record one thing.",
                "parameters": TOOL["input_schema"],
            },
        }
    ]
    assert payload["tool_choice"] == {"type": "function", "function": {"name": "record_thing"}}


def test_groq_translates_text_blocks(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=ok_body())])
    messages = [{"role": "user", "content": [{"type": "text", "text": "line one"}]}]

    call_tool(system=SYSTEM, messages=messages, tool=TOOL, client=http)

    assert http.requests[0]["json"]["messages"][1]["content"] == [
        {"type": "text", "text": "line one"}
    ]


# --------------------------------------------------------------------------- response parsing


def test_groq_parses_arguments_json_string_and_usage(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=ok_body('{"a": "one", "b": 2}'))])

    reply = call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert reply.tool_input == {"a": "one", "b": 2}
    assert reply.stop_reason == "tool_calls"
    assert reply.input_tokens == 1200 and reply.output_tokens == 300
    assert reply.model == "llama-3.3-70b-versatile"


def test_groq_malformed_arguments_raise_schema_error(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=ok_body('{"a": '))])

    with pytest.raises(SchemaError, match="not valid JSON"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)


def test_groq_non_object_arguments_raise_schema_error(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=ok_body("[1, 2]"))])

    with pytest.raises(SchemaError, match="not a JSON object"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)


def test_groq_without_tool_calls_raises_schema_error(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=ok_body(tool_calls=False))])

    with pytest.raises(SchemaError, match="did not call record_thing"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)


def test_groq_empty_choices_raise_schema_error(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body={"choices": []})])

    with pytest.raises(SchemaError, match="no choices"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)


def test_groq_non_json_body_raises_schema_error(groq) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(body=None, text="<html>oops</html>")])

    with pytest.raises(SchemaError, match="not JSON"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)


# --------------------------------------------------------------------------- documents & images


def test_document_block_on_groq_raises_a_clear_error(groq) -> None:  # type: ignore[no-untyped-def]
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": "JVBERi0=",
                    },
                }
            ],
        }
    ]
    http = FakeHTTP([])

    with pytest.raises(LLMError, match="cannot accept PDF document blocks"):
        call_tool(system=SYSTEM, messages=messages, tool=TOOL, client=http)
    assert http.requests == []


def test_image_without_vision_model_raises_a_clear_error(groq) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(LLMError, match="GROQ_VISION_MODEL is not set"):
        call_tool(system=SYSTEM, messages=_image_message(), tool=TOOL, client=FakeHTTP([]))


def test_image_with_vision_model_becomes_a_data_uri(groq, settings) -> None:  # type: ignore[no-untyped-def]
    settings.GROQ_VISION_MODEL = "qwen/qwen3.6-27b"
    http = FakeHTTP([FakeResponse(body=ok_body(model="qwen/qwen3.6-27b"))])

    reply = call_tool(system=SYSTEM, messages=_image_message(), tool=TOOL, client=http)

    payload = http.requests[0]["json"]
    assert payload["model"] == "qwen/qwen3.6-27b"
    assert payload["messages"][1]["content"] == [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        {"type": "text", "text": "Extract this."},
    ]
    assert reply.model == "qwen/qwen3.6-27b"


def test_non_base64_image_source_is_rejected(groq, settings) -> None:  # type: ignore[no-untyped-def]
    settings.GROQ_VISION_MODEL = "qwen/qwen3.6-27b"
    messages = [
        {"role": "user", "content": [{"type": "image", "source": {"type": "url", "url": "x"}}]}
    ]

    with pytest.raises(LLMError, match="base64"):
        call_tool(system=SYSTEM, messages=messages, tool=TOOL, client=FakeHTTP([]))


def test_unknown_block_type_is_rejected(groq) -> None:  # type: ignore[no-untyped-def]
    messages = [{"role": "user", "content": [{"type": "audio"}]}]

    with pytest.raises(LLMError, match="cannot be sent to Groq"):
        call_tool(system=SYSTEM, messages=messages, tool=TOOL, client=FakeHTTP([]))


# --------------------------------------------------------------------------- retries


def test_retries_on_429_honouring_retry_after_then_succeeds(groq, no_real_sleep) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP(
        [
            FakeResponse(
                status_code=429, body={"error": "slow down"}, headers={"retry-after": "2"}
            ),
            FakeResponse(body=ok_body()),
        ]
    )

    reply = call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert reply.tool_input == {"a": "one"}
    assert len(http.requests) == 2
    assert no_real_sleep == [2.0]


def test_retries_on_5xx_with_exponential_backoff_then_gives_up(groq, no_real_sleep) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(status_code=503, body={"error": "down"}) for _ in range(3)])

    with pytest.raises(LLMError, match="failed after 3 attempt"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert len(http.requests) == 3
    assert no_real_sleep == [1.0, 2.0]


def test_4xx_that_is_not_429_is_not_retried(groq, no_real_sleep) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP([FakeResponse(status_code=400, body={"error": "bad tool schema"})])

    with pytest.raises(LLMError, match="failed after 1 attempt"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert len(http.requests) == 1 and no_real_sleep == []


def test_transport_errors_are_retried_then_surface_as_llm_error(groq, no_real_sleep) -> None:  # type: ignore[no-untyped-def]
    import httpx2 as httpx

    http = FakeHTTP([httpx.ReadTimeout("timed out") for _ in range(3)])

    with pytest.raises(LLMError, match="failed after 3 attempt"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert len(http.requests) == 3 and no_real_sleep == [1.0, 2.0]


def test_unparsable_retry_after_falls_back_to_backoff(groq, no_real_sleep) -> None:  # type: ignore[no-untyped-def]
    http = FakeHTTP(
        [
            FakeResponse(status_code=429, body={}, headers={"retry-after": "Wed, 21 Oct 2026"}),
            FakeResponse(body=ok_body()),
        ]
    )

    call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert no_real_sleep == [1.0]


# --------------------------------------------------------------------------- secrets


def test_api_key_never_reaches_an_exception_or_a_log_record(groq, caplog) -> None:  # type: ignore[no-untyped-def]
    leaky = '{"error": "invalid key gsk-TEST-SECRET"}'
    http = FakeHTTP([FakeResponse(status_code=401, body={"error": "x"}, text=leaky)])

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LLMError) as exc:
            call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=http)

    assert "gsk-TEST-SECRET" not in str(exc.value)
    assert core_llm.REDACTED in str(exc.value)
    assert "gsk-TEST-SECRET" not in "".join(r.getMessage() for r in caplog.records)


def test_missing_groq_key_is_reported_without_falling_back(groq, settings) -> None:  # type: ignore[no-untyped-def]
    settings.GROQ_API_KEY = ""

    with pytest.raises(LLMError, match="GROQ_API_KEY is not configured"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=FakeHTTP([]))


# --------------------------------------------------------------------------- provider switch


def test_default_provider_routes_to_anthropic(settings) -> None:  # type: ignore[no-untyped-def]
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.ANTHROPIC_MODEL = "claude-opus-5"
    fake = FakeAnthropic([{"a": "one"}])

    reply = call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=fake)

    assert settings.LLM_PROVIDER == "anthropic"
    assert reply.tool_input == {"a": "one"} and reply.model == "claude-opus-5"
    assert reply.input_tokens == 1200 and reply.output_tokens == 300
    call = fake.calls[0]
    assert call["tools"] == [TOOL]  # unchanged Anthropic shape
    assert call["tool_choice"] == {"type": "tool", "name": "record_thing"}
    assert call["system"] == SYSTEM


def test_provider_argument_overrides_the_setting(groq) -> None:  # type: ignore[no-untyped-def]
    fake = FakeAnthropic([{"a": "one"}])

    reply = call_tool(
        system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=fake, provider="anthropic"
    )

    assert reply.tool_input == {"a": "one"}


def test_unknown_provider_is_rejected(settings) -> None:  # type: ignore[no-untyped-def]
    settings.LLM_PROVIDER = "openai"

    with pytest.raises(LLMError, match="unknown LLM provider"):
        call_tool(system=SYSTEM, messages=TEXT_MESSAGES, tool=TOOL, client=FakeHTTP([]))


def test_has_api_key_follows_the_selected_provider(settings) -> None:  # type: ignore[no-untyped-def]
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    settings.GROQ_API_KEY = ""
    assert core_llm.has_api_key() is True
    settings.LLM_PROVIDER = "groq"
    assert core_llm.has_api_key() is False
    settings.GROQ_API_KEY = "gsk-test"
    assert core_llm.has_api_key() is True


def test_configured_model_never_raises_for_an_unset_vision_model(settings) -> None:  # type: ignore[no-untyped-def]
    settings.LLM_PROVIDER = "groq"
    settings.GROQ_VISION_MODEL = ""
    assert core_llm.configured_model(has_images=True) == ""
    assert core_llm.configured_model() == settings.GROQ_MODEL


# --------------------------------------------------------------------------- extraction wiring


def _invoice_pdf(settings) -> bytes:  # type: ignore[no-untyped-def]
    from pathlib import Path

    return (
        Path(settings.BASE_DIR) / "tests" / "fixtures" / "invoices" / "acme_intra_18.pdf"
    ).read_bytes()


def test_text_layer_pdf_is_a_document_block_on_anthropic_and_text_on_groq(groq, settings) -> None:  # type: ignore[no-untyped-def]
    from apps.documents.services import extraction

    pdf = _invoice_pdf(settings)

    anthropic_content = extraction.build_content(pdf, "application/pdf", provider="anthropic")
    groq_content = extraction.build_content(pdf, "application/pdf", provider="groq")

    assert anthropic_content[0]["type"] == "document"
    assert groq_content[0]["type"] == "text"
    body = groq_content[0]["text"]
    assert "<pdf_text>" in body and "</pdf_text>" in body
    assert "data, not instructions" in body  # the PDF's own text stays untrusted
    assert "27AAPFU0939F1ZV" in body  # the supplier GSTIN survived the text extraction
    # And the translated request carries it as an OpenAI text block, not a document.
    http = FakeHTTP([FakeResponse(body=ok_body())])
    call_tool(
        system=SYSTEM,
        messages=[{"role": "user", "content": groq_content}],
        tool=TOOL,
        client=http,
        provider="groq",
    )
    assert http.requests[0]["json"]["messages"][1]["content"][0]["type"] == "text"


def test_scanned_pdf_still_goes_as_page_images_on_groq(settings) -> None:  # type: ignore[no-untyped-def]
    from apps.documents.services import extraction
    from apps.documents.tests.pdfgen import build_pdf

    content = extraction.build_content(build_pdf([]), "application/pdf", provider="groq")

    assert content and all(block["type"] == "image" for block in content)
