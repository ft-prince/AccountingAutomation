"""Common provider interface. PROJECT_SPECS §6.3.

Each provider module exposes:
    fetch_new(connection) -> FetchResult          # new messages since connection.sync_cursor
    profile_email(tokens) -> str                  # mailbox address after OAuth
    revoke(tokens) -> bool                        # best effort; False when unreachable
    _provider_send_<name>(...)                    # ONLY called from services.send_via_provider
"""

from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class RawAttachment:
    filename: str
    mime: str
    data: bytes


@dataclass(frozen=True)
class RawMessage:
    provider_message_id: str
    provider_thread_id: str
    from_address: str
    to: list[str]
    cc: list[str]
    date: datetime
    subject: str
    body_text: str
    body_html: str
    attachments: list[RawAttachment] = field(default_factory=list)
    is_read: bool = False
    rfc_message_id: str = ""


@dataclass(frozen=True)
class FetchResult:
    messages: list[RawMessage]
    cursor: str  # historyId (Gmail) / deltaLink (Graph) to persist after a successful sync
    tokens: dict[str, Any] | None = None  # refreshed credentials to re-encrypt, if they changed


def provider_module(provider: str) -> ModuleType:
    if provider == "gmail":
        from apps.mail.providers import gmail

        return gmail
    if provider == "microsoft":
        from apps.mail.providers import graph

        return graph
    raise ValueError(f"unknown mail provider: {provider}")
