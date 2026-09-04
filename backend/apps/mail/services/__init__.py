"""THE single outbound-mail gateway. CLAUDE.md §4, PROJECT_SPECS §6.1.

`send_via_provider` is the only function in the codebase that reaches a provider send API.
It requires exactly one of reviewer_id (a human-approved draft) or report_schedule_id
(a fixed-content §7.3 report). A grep test (tests/test_gateway.py) fails if
`_provider_send_gmail` / `_provider_send_graph` are referenced anywhere else."""

import logging
from typing import Any

from apps.mail.crypto import decrypt_tokens
from apps.mail.models import EmailMessage, MessageDirection, Provider
from apps.mail.providers.gmail import _provider_send_gmail
from apps.mail.providers.graph import _provider_send_graph

log = logging.getLogger(__name__)


class SendError(Exception):
    pass


def _in_reply_to(message: EmailMessage) -> tuple[str, str]:
    """(RFC Message-ID to reply to, provider thread id) from the thread's latest inbound."""
    if message.thread is None:
        return "", ""
    inbound = (
        EmailMessage.objects.filter(thread=message.thread, direction=MessageDirection.INBOUND)
        .order_by("-date")
        .first()
    )
    return (inbound.rfc_message_id if inbound else "", message.thread.provider_thread_id)


def send_via_provider(
    message: EmailMessage,
    *,
    reviewer_id: Any = None,
    report_schedule_id: Any = None,
) -> str:
    """Send `message` through its mailbox's provider. Returns the provider message id ('' for
    Graph, whose send endpoint returns no id). Raises ValueError unless exactly one authority
    is given; SendError when the mailbox cannot send."""
    if (reviewer_id is None) == (report_schedule_id is None):
        raise ValueError("send_via_provider needs exactly one of reviewer_id / report_schedule_id")
    if message.direction != MessageDirection.OUTBOUND:
        raise ValueError("only outbound messages can be sent")
    mailbox = message.mailbox
    if not mailbox.has_send_scope:
        raise SendError("mailbox has not granted the send scope")
    if not message.to_addresses:
        raise SendError("message has no recipients")
    tokens = decrypt_tokens(mailbox.encrypted_tokens)
    in_reply_to, thread_id = _in_reply_to(message)
    kwargs: dict[str, Any] = {
        "from_address": mailbox.email_address,
        "to": list(message.to_addresses),
        "cc": list(message.cc_addresses),
        "subject": message.subject,
        "body_text": message.body_text,
        "body_html": message.body_html,
        "in_reply_to": in_reply_to,
        "provider_thread_id": thread_id,
    }
    log.info(
        "send_via_provider",
        extra={
            "mailbox_id": str(mailbox.pk),
            "reviewer_id": str(reviewer_id) if reviewer_id else None,
            "report_schedule_id": str(report_schedule_id) if report_schedule_id else None,
        },
    )
    if mailbox.provider == Provider.GMAIL:
        return _provider_send_gmail(tokens, **kwargs)
    return _provider_send_graph(tokens, **kwargs)
