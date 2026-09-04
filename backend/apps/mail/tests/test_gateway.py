"""THE gateway (CLAUDE.md §4, PROJECT_SPECS §6.1, §13): the provider send API is reachable from
exactly one function, which requires reviewer_id xor report_schedule_id. A grep over the codebase
proves it."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps.mail import services as gateway
from apps.mail.factories import MailboxFactory, MessageFactory, ThreadFactory
from apps.mail.models import EmailMessage, MessageDirection
from apps.mail.providers.gmail import READ_SCOPES, SEND_SCOPE
from apps.mail.providers.graph import SEND_SCOPE as GRAPH_SEND_SCOPE

BACKEND = Path(__file__).resolve().parents[3]
ROOTS = (BACKEND / "apps", BACKEND / "config")
GMAIL_PROVIDER = BACKEND / "apps" / "mail" / "providers" / "gmail.py"
GRAPH_PROVIDER = BACKEND / "apps" / "mail" / "providers" / "graph.py"
GATEWAY_MODULE = BACKEND / "apps" / "mail" / "services" / "__init__.py"

# token → the only files allowed to contain it (tests excluded)
ALLOWED: dict[str, set[Path]] = {
    "messages().send(": {GMAIL_PROVIDER},
    "/sendMail": {GRAPH_PROVIDER},
    "_provider_send_gmail": {GMAIL_PROVIDER, GATEWAY_MODULE},
    "_provider_send_graph": {GRAPH_PROVIDER, GATEWAY_MODULE},
}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def test_gateway_module_is_where_we_think() -> None:
    assert Path(gateway.__file__).resolve() == GATEWAY_MODULE
    assert GMAIL_PROVIDER.exists() and GRAPH_PROVIDER.exists()


@pytest.mark.parametrize("token", sorted(ALLOWED))
def test_provider_send_api_is_called_from_exactly_one_gateway(token: str) -> None:
    offenders = sorted(
        str(path.relative_to(BACKEND))
        for path in _source_files()
        if token in path.read_text() and path not in ALLOWED[token]
    )
    assert offenders == [], f"{token!r} may only appear in {ALLOWED[token]}"
    assert all(token in path.read_text() for path in ALLOWED[token])


def test_no_other_module_builds_a_gmail_send_or_graph_sendmail_call() -> None:
    """Belt and braces: nothing outside the provider files even mentions the send endpoints."""
    for path in _source_files():
        text = path.read_text()
        if path not in (GMAIL_PROVIDER, GRAPH_PROVIDER):
            assert ".send(userId" not in text, path
            assert "sendMail" not in text, path


# ---------------------------------------------------------------- send_via_provider contract


def outbound(org, *, thread=None, mailbox=None, to=("a@b.example",)):  # type: ignore[no-untyped-def]
    mailbox = mailbox or (
        thread.mailbox if thread else MailboxFactory(org=org, scopes=[*READ_SCOPES, SEND_SCOPE])
    )
    return EmailMessage(
        org=org,
        mailbox=mailbox,
        thread=thread,
        direction=MessageDirection.OUTBOUND,
        from_address=mailbox.email_address,
        to_addresses=list(to),
        date=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        subject="Monthly report",
        body_text="Attached.",
    )


@pytest.mark.django_db
def test_requires_exactly_one_authority(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict] = []  # type: ignore[type-arg]
    monkeypatch.setattr(
        gateway, "_provider_send_gmail", lambda tokens, **kw: calls.append(kw) or "id"
    )
    message = outbound(org_a.org)
    with pytest.raises(ValueError, match="exactly one"):
        gateway.send_via_provider(message)
    with pytest.raises(ValueError, match="exactly one"):
        gateway.send_via_provider(
            message, reviewer_id=uuid.uuid4(), report_schedule_id=uuid.uuid4()
        )
    inbound = outbound(org_a.org)
    inbound.direction = MessageDirection.INBOUND
    with pytest.raises(ValueError, match="outbound"):
        gateway.send_via_provider(inbound, reviewer_id=uuid.uuid4())
    assert calls == []


@pytest.mark.django_db
def test_report_schedule_path_sends_a_threadless_message(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict] = []  # type: ignore[type-arg]
    monkeypatch.setattr(
        gateway, "_provider_send_gmail", lambda tokens, **kw: calls.append(kw) or "g-1"
    )
    message = outbound(org_a.org)  # §6.1: report mails have no thread
    assert gateway.send_via_provider(message, report_schedule_id=uuid.uuid4()) == "g-1"
    assert calls[0]["in_reply_to"] == "" and calls[0]["provider_thread_id"] == ""
    assert calls[0]["to"] == ["a@b.example"] and calls[0]["subject"] == "Monthly report"


@pytest.mark.django_db
def test_reply_path_threads_on_latest_inbound(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict] = []  # type: ignore[type-arg]
    monkeypatch.setattr(
        gateway, "_provider_send_gmail", lambda tokens, **kw: calls.append(kw) or "g-2"
    )
    mailbox = MailboxFactory(org=org_a.org, scopes=[*READ_SCOPES, SEND_SCOPE])
    thread = ThreadFactory(org=org_a.org, mailbox=mailbox, provider_thread_id="t-42")
    MessageFactory(
        thread=thread, rfc_message_id="<old@x>", date=datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    )
    MessageFactory(
        thread=thread, rfc_message_id="<new@x>", date=datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    )
    gateway.send_via_provider(outbound(org_a.org, thread=thread), reviewer_id=uuid.uuid4())
    assert calls[0]["in_reply_to"] == "<new@x>" and calls[0]["provider_thread_id"] == "t-42"


@pytest.mark.django_db
def test_graph_mailboxes_route_to_the_graph_send(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    graph_calls: list[dict] = []  # type: ignore[type-arg]
    monkeypatch.setattr(
        gateway, "_provider_send_graph", lambda tokens, **kw: graph_calls.append(kw) or ""
    )
    monkeypatch.setattr(
        gateway, "_provider_send_gmail", lambda tokens, **kw: pytest.fail("wrong provider")
    )
    mailbox = MailboxFactory(
        org=org_a.org, provider="microsoft", scopes=["Mail.Read", GRAPH_SEND_SCOPE]
    )
    assert (
        gateway.send_via_provider(outbound(org_a.org, mailbox=mailbox), reviewer_id=uuid.uuid4())
        == ""
    )
    assert len(graph_calls) == 1


@pytest.mark.django_db
def test_refuses_without_send_scope_recipients_or_tokens(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        gateway, "_provider_send_gmail", lambda tokens, **kw: pytest.fail("must not send")
    )
    read_only = MailboxFactory(org=org_a.org)
    with pytest.raises(gateway.SendError, match="send scope"):
        gateway.send_via_provider(outbound(org_a.org, mailbox=read_only), reviewer_id=uuid.uuid4())
    with pytest.raises(gateway.SendError, match="recipients"):
        gateway.send_via_provider(outbound(org_a.org, to=()), reviewer_id=uuid.uuid4())
    revoked = MailboxFactory(org=org_a.org, scopes=[SEND_SCOPE], encrypted_tokens="")
    with pytest.raises(ValueError, match="no stored credentials"):
        gateway.send_via_provider(outbound(org_a.org, mailbox=revoked), reviewer_id=uuid.uuid4())
