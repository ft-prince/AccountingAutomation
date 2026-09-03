"""A stand-in for anthropic.Anthropic that replays recorded tool inputs."""

from types import SimpleNamespace
from typing import Any


class FakeAnthropic:
    def __init__(self, replies: list[dict[str, Any] | None], *, stop_reason: str = "tool_use"):
        self._replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)
        self.stop_reason = stop_reason

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        tool_input = self._replies.pop(0) if self._replies else None
        content = (
            [SimpleNamespace(type="tool_use", name="record_invoice", input=tool_input)]
            if tool_input is not None
            else [SimpleNamespace(type="text", text="I cannot.")]
        )
        return SimpleNamespace(
            content=content,
            usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
            stop_reason=self.stop_reason,
            to_dict=lambda: {"content": [{"type": "tool_use", "input": tool_input}]},
        )
