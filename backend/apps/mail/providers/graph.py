"""Microsoft Graph provider. PROJECT_SPECS §6.3: delta query on the inbox every 2 min.
Send lives in `_provider_send_graph`, called ONLY from apps.mail.services.send_via_provider."""

import base64
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import msal
import requests
from django.conf import settings

from apps.mail.providers import FetchResult, RawAttachment, RawMessage

log = logging.getLogger(__name__)

AUTHORITY = "https://login.microsoftonline.com/common"
GRAPH = "https://graph.microsoft.com/v1.0"
READ_SCOPES = ["Mail.Read", "User.Read"]  # msal adds offline_access / openid / profile itself
SEND_SCOPE = "Mail.Send"
FIRST_SYNC_DAYS = 30
HTTP_TIMEOUT = 30
SELECT = (
    "id,conversationId,subject,from,toRecipients,ccRecipients,receivedDateTime,"
    "body,isRead,hasAttachments,internetMessageId"
)


class GraphError(Exception):
    pass


def _app() -> Any:
    return msal.ConfidentialClientApplication(
        settings.MICROSOFT_OAUTH_CLIENT_ID,
        authority=AUTHORITY,
        client_credential=settings.MICROSOFT_OAUTH_CLIENT_SECRET,
    )


def initiate_flow(scopes: list[str], *, state: str, redirect_uri: str) -> dict[str, Any]:
    flow: dict[str, Any] = _app().initiate_auth_code_flow(
        scopes, redirect_uri=redirect_uri, state=state
    )
    return flow


def exchange_flow(flow: dict[str, Any], query: dict[str, str]) -> dict[str, Any]:
    result = _app().acquire_token_by_auth_code_flow(flow, query)
    return _tokens_from_result(result, list(flow.get("scope", [])))


def _tokens_from_result(result: dict[str, Any], scopes: list[str]) -> dict[str, Any]:
    if "access_token" not in result:
        raise GraphError(result.get("error_description") or "token exchange failed")
    granted = str(result.get("scope", "")).split() or scopes
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expires_at": time.time() + int(result.get("expires_in", 0)),
        "scopes": [s.split("/")[-1] for s in granted if not s.startswith(("openid", "profile"))],
        "email": (result.get("id_token_claims") or {}).get("preferred_username", ""),
    }


def access_token(tokens: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Return (bearer, refreshed_tokens_or_None); refreshes server-side when expired."""
    if tokens.get("access_token") and time.time() < float(tokens.get("expires_at", 0)) - 60:
        return str(tokens["access_token"]), None
    if not tokens.get("refresh_token"):
        raise GraphError("no refresh token; reconnect the mailbox")
    scopes = [s for s in tokens.get("scopes", []) if s != "offline_access"]
    result = _app().acquire_token_by_refresh_token(tokens["refresh_token"], scopes=scopes)
    refreshed = _tokens_from_result(result, scopes)
    refreshed["email"] = tokens.get("email", refreshed["email"])
    return str(refreshed["access_token"]), refreshed


def _get(url: str, bearer: str) -> dict[str, Any]:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {bearer}", "Prefer": 'outlook.body-content-type="html"'},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GraphError(f"GET {url.split('?')[0]} → {resp.status_code}")
    data: dict[str, Any] = resp.json()
    return data


def _post(url: str, bearer: str, body: dict[str, Any]) -> int:
    resp = requests.post(
        url, headers={"Authorization": f"Bearer {bearer}"}, json=body, timeout=HTTP_TIMEOUT
    )
    if resp.status_code >= 400:
        raise GraphError(f"POST {url} → {resp.status_code}")
    return int(resp.status_code)


def profile_email(tokens: dict[str, Any]) -> str:
    if tokens.get("email"):
        return str(tokens["email"])
    bearer, _ = access_token(tokens)
    me = _get(f"{GRAPH}/me?$select=mail,userPrincipalName", bearer)
    return str(me.get("mail") or me.get("userPrincipalName") or "")


def revoke(tokens: dict[str, Any]) -> bool:
    """Graph has no per-app refresh-token revocation endpoint; tokens are dropped locally."""
    return False


# ---------------------------------------------------------------- parsing (pure)


def _recipients(items: list[dict[str, Any]]) -> list[str]:
    return [
        str(i.get("emailAddress", {}).get("address", "")).lower()
        for i in items
        if i.get("emailAddress", {}).get("address")
    ]


def _parse_date(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)


def parse_message(item: dict[str, Any], attachments: list[dict[str, Any]]) -> RawMessage:
    body = item.get("body", {})
    is_html = str(body.get("contentType", "")).lower() == "html"
    content = str(body.get("content", ""))
    return RawMessage(
        provider_message_id=str(item["id"]),
        provider_thread_id=str(item.get("conversationId") or item["id"]),
        from_address=_recipients([item.get("from", {})])[0] if item.get("from") else "",
        to=_recipients(item.get("toRecipients", [])),
        cc=_recipients(item.get("ccRecipients", [])),
        date=_parse_date(str(item.get("receivedDateTime", "1970-01-01T00:00:00Z"))),
        subject=str(item.get("subject") or ""),
        body_text="" if is_html else content,
        body_html=content if is_html else "",
        attachments=[
            RawAttachment(
                filename=str(a.get("name", "")),
                mime=str(a.get("contentType", "")),
                data=base64.b64decode(a["contentBytes"]),
            )
            for a in attachments
            if a.get("contentBytes")
        ],
        is_read=bool(item.get("isRead", False)),
        rfc_message_id=str(item.get("internetMessageId") or ""),
    )


# ---------------------------------------------------------------- sync


def _first_sync_url() -> str:
    since = (datetime.now(tz=UTC) - timedelta(days=FIRST_SYNC_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{GRAPH}/me/mailFolders/inbox/messages/delta?$select={SELECT}"
        f"&$filter=receivedDateTime ge {since}"
    )


def fetch_new(connection: Any) -> FetchResult:
    from apps.mail.crypto import decrypt_tokens

    tokens = decrypt_tokens(connection.encrypted_tokens)
    bearer, refreshed = access_token(tokens)
    url = connection.sync_cursor or _first_sync_url()
    messages: list[RawMessage] = []
    while True:
        page = _get(url, bearer)
        for item in page.get("value", []):
            if "@removed" in item:
                continue
            attachments: list[dict[str, Any]] = []
            if item.get("hasAttachments"):
                attachments = _get(f"{GRAPH}/me/messages/{item['id']}/attachments", bearer).get(
                    "value", []
                )
            messages.append(parse_message(item, attachments))
        if page.get("@odata.nextLink"):
            url = str(page["@odata.nextLink"])
            continue
        return FetchResult(
            messages=messages, cursor=str(page.get("@odata.deltaLink", "")), tokens=refreshed
        )


# ---------------------------------------------------------------- send (gateway-only)


def _provider_send_graph(
    tokens: dict[str, Any],
    *,
    from_address: str,
    to: list[str],
    cc: list[str],
    subject: str,
    body_text: str,
    body_html: str,
    in_reply_to: str,
    provider_thread_id: str,
) -> str:
    """The Graph send call. Never call this directly — go through send_via_provider.
    /sendMail returns 202 with no id, so the provider message id is empty."""
    bearer, _ = access_token(tokens)
    message: dict[str, Any] = {
        "subject": subject,
        "body": {
            "contentType": "HTML" if body_html else "Text",
            "content": body_html or body_text,
        },
        "toRecipients": [{"emailAddress": {"address": a}} for a in to],
        "ccRecipients": [{"emailAddress": {"address": a}} for a in cc],
    }
    if in_reply_to:
        message["internetMessageHeaders"] = [{"name": "In-Reply-To", "value": in_reply_to}]
    _post(f"{GRAPH}/me/sendMail", bearer, {"message": message, "saveToSentItems": True})
    return ""
