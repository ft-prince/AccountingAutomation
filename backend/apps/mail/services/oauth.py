"""OAuth connect / progressive send-scope consent / revoke. PROJECT_SPECS §6.3, §12.
Tokens are encrypted before they touch the database; state lives in the Django session."""

import logging
import secrets
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.audit import record
from apps.mail.crypto import decrypt_tokens, encrypt_tokens
from apps.mail.models import MailboxConnection, MailboxStatus, Provider
from apps.mail.providers import gmail, graph

log = logging.getLogger(__name__)

SESSION_KEY = "mail_oauth"


class OAuthError(ValueError):
    pass


def _redirect_uri(provider: str) -> str:
    base = settings.OAUTH_REDIRECT_BASE.rstrip("/")
    if not base:
        raise OAuthError("OAUTH_REDIRECT_BASE is not configured")
    return f"{base}/api/mail/connect/{provider}/callback"


def _configured(provider: str) -> None:
    if provider == Provider.GMAIL and not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise OAuthError("GOOGLE_OAUTH_CLIENT_ID is not configured")
    if provider == Provider.MICROSOFT and not settings.MICROSOFT_OAUTH_CLIENT_ID:
        raise OAuthError("MICROSOFT_OAUTH_CLIENT_ID is not configured")


def read_scopes(provider: str) -> list[str]:
    return list(gmail.READ_SCOPES if provider == Provider.GMAIL else graph.READ_SCOPES)


def send_scope(provider: str) -> str:
    return gmail.SEND_SCOPE if provider == Provider.GMAIL else graph.SEND_SCOPE


def start_connect(
    session: Any, *, org: Any, provider: str, mailbox: MailboxConnection | None = None
) -> str:
    """Return the provider authorization URL; remember state in the session for the callback.
    With `mailbox` this is the second consent step that adds the send scope (§6.3)."""
    if provider not in Provider.values:
        raise OAuthError(f"unknown provider: {provider}")
    _configured(provider)
    scopes = read_scopes(provider)
    if mailbox is not None:
        scopes = list(dict.fromkeys([*mailbox.scopes, *scopes, send_scope(provider)]))
    state = secrets.token_urlsafe(32)
    redirect_uri = _redirect_uri(provider)
    pending: dict[str, Any] = {
        "state": state,
        "provider": provider,
        "org_id": str(org.pk),
        "mailbox_id": str(mailbox.pk) if mailbox else None,
        "scopes": scopes,
    }
    if provider == Provider.GMAIL:
        url, code_verifier = gmail.authorization_url(scopes, state=state, redirect_uri=redirect_uri)
        pending["code_verifier"] = code_verifier
    else:
        flow = graph.initiate_flow(scopes, state=state, redirect_uri=redirect_uri)
        pending["flow"] = flow
        url = str(flow["auth_uri"])
    session[SESSION_KEY] = pending
    return url


def _provider_hint(provider: str, exc: Exception) -> str:
    """Turn a provider SDK exception into something a person can act on."""
    text = str(exc)
    if "accessNotConfigured" in text or "has not been used in project" in text:
        api = "Gmail API" if provider == Provider.GMAIL else "Microsoft Graph"
        return (
            f"{api} is not enabled for this OAuth project. Enable it in the provider console, "
            "wait a minute for it to propagate, then connect again."
        )
    if "insufficientPermissions" in text or "insufficient" in text.lower():
        return (
            "The granted scopes are insufficient. Disconnect and connect again, "
            "accepting all requested permissions."
        )
    if "invalid_grant" in text:
        return "The authorisation code was rejected. Start the connection again."
    return f"The provider rejected the request: {text[:300]}"


def _exchange(pending: dict[str, Any], query: dict[str, str]) -> dict[str, Any]:
    provider = pending["provider"]
    if provider == Provider.GMAIL:
        return gmail.exchange_code(
            query["code"],
            scopes=pending["scopes"],
            redirect_uri=_redirect_uri(provider),
            code_verifier=pending.get("code_verifier", ""),
        )
    return graph.exchange_flow(pending["flow"], query)


def complete_connect(
    session: Any, *, org: Any, user: Any, provider: str, query: dict[str, str]
) -> MailboxConnection:
    pending = session.pop(SESSION_KEY, None)
    if not pending or pending["provider"] != provider or pending["org_id"] != str(org.pk):
        raise OAuthError("no pending OAuth flow for this provider")
    if query.get("error"):
        raise OAuthError(f"provider returned an error: {query['error']}")
    if not query.get("code") or query.get("state") != pending["state"]:
        raise OAuthError("OAuth state mismatch")
    try:
        tokens = _exchange(pending, query)
    except OAuthError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface a message, not a traceback
        raise OAuthError(_provider_hint(provider, exc)) from exc
    module = gmail if provider == Provider.GMAIL else graph
    try:
        email_address = module.profile_email(tokens).lower()
    except Exception as exc:  # noqa: BLE001 — any provider failure becomes a readable message
        raise OAuthError(_provider_hint(provider, exc)) from exc
    granted = list(tokens.get("scopes") or pending["scopes"])
    with transaction.atomic():
        if pending.get("mailbox_id"):
            mailbox = MailboxConnection.objects.for_org(org).get(pk=pending["mailbox_id"])
            if mailbox.email_address.lower() != email_address:
                raise OAuthError("consent was given for a different mailbox")
            created = False
        else:
            mailbox, created = MailboxConnection.objects.get_or_create(
                org=org,
                provider=provider,
                email_address=email_address,
                defaults={"connected_by": user},
            )
        mailbox.encrypted_tokens = encrypt_tokens(tokens)
        mailbox.scopes = granted
        mailbox.status = MailboxStatus.ACTIVE
        mailbox.last_error = ""
        if mailbox.has_send_scope:
            mailbox.needs_send_scope = False
        mailbox.save()
        record(
            org,
            actor=user,
            entity=mailbox,
            action="mailbox.connect" if created else "mailbox.reauthorize",
            after={"provider": provider, "email": email_address, "scopes": granted},
        )
    return mailbox


def revoke_mailbox(mailbox: MailboxConnection, *, actor: Any) -> MailboxConnection:
    """Revoke with the provider if reachable; always clear local tokens."""
    revoked_remotely = False
    if mailbox.encrypted_tokens:
        module = gmail if mailbox.provider == Provider.GMAIL else graph
        try:
            revoked_remotely = bool(module.revoke(decrypt_tokens(mailbox.encrypted_tokens)))
        except Exception:  # noqa: BLE001 — best effort; local revocation must proceed
            log.warning("provider revoke failed", extra={"mailbox_id": str(mailbox.pk)})
    before = {"status": mailbox.status, "scopes": list(mailbox.scopes)}
    mailbox.encrypted_tokens = ""
    mailbox.scopes = []
    mailbox.status = MailboxStatus.REVOKED
    mailbox.sync_cursor = ""
    mailbox.last_sync_at = mailbox.last_sync_at or timezone.now()
    mailbox.save()
    record(
        mailbox.org,
        actor=actor,
        entity=mailbox,
        action="mailbox.revoke",
        before=before,
        after={"status": mailbox.status, "revoked_remotely": revoked_remotely},
    )
    return mailbox
