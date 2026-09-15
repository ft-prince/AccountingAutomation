"""Gmail provider. PROJECT_SPECS §6.3: poll history.list every 2 min; first sync = last 30 days.
Send lives in `_provider_send_gmail`, called ONLY from apps.mail.services.send_via_provider."""

import base64
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage as MimeMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

import requests
from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.mail.providers import FetchResult, RawAttachment, RawMessage

log = logging.getLogger(__name__)

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
LABELS_SCOPE = "https://www.googleapis.com/auth/gmail.labels"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
# gmail.modify would already permit messages.send, which defeats progressive consent (§6.3),
# so "modify labels" is requested as gmail.labels and send is a separate consent step.
READ_SCOPES = [READONLY_SCOPE, LABELS_SCOPE]
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
FIRST_SYNC_FILTER = "-in:spam -in:trash -in:draft"
PAGE_SIZE = 100
HTTP_TIMEOUT = 15


class GmailError(Exception):
    pass


def _client_config(redirect_uri: str) -> dict[str, Any]:
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": [redirect_uri],
        }
    }


def _flow(scopes: list[str], redirect_uri: str) -> Any:
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(redirect_uri), scopes=scopes)
    flow.redirect_uri = redirect_uri
    return flow


def authorization_url(scopes: list[str], *, state: str, redirect_uri: str) -> tuple[str, str]:
    """Returns (url, code_verifier). The library generates a PKCE verifier here and Google only
    sees its challenge, so the caller MUST carry the verifier to the token exchange or Google
    rejects it with "Missing code verifier"."""
    flow = _flow(scopes, redirect_uri)
    url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true", state=state
    )
    return str(url), str(getattr(flow, "code_verifier", "") or "")


def exchange_code(
    code: str, *, scopes: list[str], redirect_uri: str, code_verifier: str = ""
) -> dict[str, Any]:
    flow = _flow(scopes, redirect_uri)
    if code_verifier:
        flow.code_verifier = code_verifier
    # Google returns every scope the user has ever granted this app (e.g. gmail.send from an
    # earlier consent), which oauthlib treats as an error unless told the superset is fine.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    flow.fetch_token(code=code)
    return tokens_from_credentials(flow.credentials)


def tokens_from_credentials(creds: Any) -> dict[str, Any]:
    """Only what is needed to rebuild Credentials; the client secret stays in settings."""
    expiry = getattr(creds, "expiry", None)
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": TOKEN_URI,
        "scopes": list(creds.scopes or []),
        "expiry": expiry.isoformat() if expiry else None,
    }


def credentials(tokens: dict[str, Any]) -> Credentials:
    return Credentials(
        token=tokens.get("token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=TOKEN_URI,
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=tokens.get("scopes") or None,
    )


def service(tokens: dict[str, Any]) -> Any:
    return build("gmail", "v1", credentials=credentials(tokens), cache_discovery=False)


def profile_email(tokens: dict[str, Any]) -> str:
    profile = service(tokens).users().getProfile(userId="me").execute()
    return str(profile["emailAddress"])


def revoke(tokens: dict[str, Any]) -> bool:
    token = tokens.get("refresh_token") or tokens.get("token")
    if not token:
        return False
    try:
        resp = requests.post(REVOKE_URI, params={"token": token}, timeout=HTTP_TIMEOUT)
    except requests.RequestException:
        log.warning("gmail revoke unreachable")
        return False
    return resp.status_code == 200


# ---------------------------------------------------------------- parsing (pure)


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _walk(part: dict[str, Any], out: list[dict[str, Any]]) -> None:
    out.append(part)
    for child in part.get("parts", []):
        _walk(child, out)


def _addresses(raw: str) -> list[str]:
    return [addr.lower() for _, addr in getaddresses([raw]) if addr]


def _message_date(headers: dict[str, str], msg: dict[str, Any]) -> datetime:
    if headers.get("date"):
        try:
            parsed = parsedate_to_datetime(headers["date"])
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass
    return datetime.fromtimestamp(int(msg.get("internalDate", 0)) / 1000, tz=UTC)


def parse_message(
    msg: dict[str, Any], fetch_attachment: Callable[[str, str], bytes] | None = None
) -> RawMessage:
    """users.messages.get(format=full) payload → RawMessage. No network unless attachments."""
    payload = msg.get("payload", {})
    headers = _headers(payload)
    parts: list[dict[str, Any]] = []
    _walk(payload, parts)
    text, html = "", ""
    attachments: list[RawAttachment] = []
    for part in parts:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        filename = part.get("filename") or ""
        if filename and fetch_attachment is not None:
            data = (
                _b64url_decode(body["data"])
                if body.get("data")
                else fetch_attachment(msg["id"], body.get("attachmentId", ""))
            )
            attachments.append(RawAttachment(filename=filename, mime=mime, data=data))
        elif mime == "text/plain" and body.get("data") and not text:
            text = _b64url_decode(body["data"]).decode("utf-8", errors="replace")
        elif mime == "text/html" and body.get("data") and not html:
            html = _b64url_decode(body["data"]).decode("utf-8", errors="replace")
    labels = set(msg.get("labelIds", []))
    return RawMessage(
        provider_message_id=str(msg["id"]),
        provider_thread_id=str(msg.get("threadId", msg["id"])),
        from_address=parseaddr(headers.get("from", ""))[1].lower(),
        to=_addresses(headers.get("to", "")),
        cc=_addresses(headers.get("cc", "")),
        date=_message_date(headers, msg),
        subject=headers.get("subject", ""),
        body_text=text,
        body_html=html,
        attachments=attachments,
        is_read="UNREAD" not in labels,
        rfc_message_id=headers.get("message-id", ""),
    )


# ---------------------------------------------------------------- sync


def _history_ids(svc: Any, cursor: str) -> list[str]:
    ids: list[str] = []
    token: str | None = None
    while True:
        resp = (
            svc.users()
            .history()
            .list(
                userId="me",
                startHistoryId=cursor,
                historyTypes=["messageAdded"],
                pageToken=token,
                maxResults=PAGE_SIZE,
            )
            .execute()
        )
        for entry in resp.get("history", []):
            ids.extend(str(m["message"]["id"]) for m in entry.get("messagesAdded", []))
        token = resp.get("nextPageToken")
        if not token:
            return list(dict.fromkeys(ids))


def _recent_ids(svc: Any) -> list[str]:
    """First sync: newest MAIL_FIRST_SYNC_LIMIT messages from the last MAIL_FIRST_SYNC_DAYS."""
    limit = int(settings.MAIL_FIRST_SYNC_LIMIT)
    query = f"newer_than:{int(settings.MAIL_FIRST_SYNC_DAYS)}d {FIRST_SYNC_FILTER}"
    ids: list[str] = []
    token: str | None = None
    while len(ids) < limit:
        resp = (
            svc.users()
            .messages()
            .list(
                userId="me", q=query, pageToken=token, maxResults=min(PAGE_SIZE, limit - len(ids))
            )
            .execute()
        )
        ids.extend(str(m["id"]) for m in resp.get("messages", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def fetch_new(connection: Any) -> FetchResult:
    from apps.mail.crypto import decrypt_tokens

    tokens = decrypt_tokens(connection.encrypted_tokens)
    creds = credentials(tokens)
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    ids: list[str]
    if connection.sync_cursor:
        try:
            ids = _history_ids(svc, connection.sync_cursor)
        except HttpError as exc:  # 404: history expired → full resync
            if exc.resp.status != 404:
                raise
            ids = _recent_ids(svc)
    else:
        ids = _recent_ids(svc)

    def fetch_attachment(message_id: str, attachment_id: str) -> bytes:
        att = (
            svc.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return _b64url_decode(att["data"])

    messages: list[RawMessage] = []
    for mid in ids:
        try:
            msg = svc.users().messages().get(userId="me", id=mid, format="full").execute()
        except HttpError as exc:  # deleted between listing and fetching: skip, keep syncing
            if exc.resp.status != 404:
                raise
            log.info("gmail message vanished before fetch", extra={"message_id": mid})
            continue
        messages.append(parse_message(msg, fetch_attachment))
    profile = svc.users().getProfile(userId="me").execute()
    refreshed = tokens_from_credentials(creds) if creds.token != tokens.get("token") else None
    return FetchResult(messages=messages, cursor=str(profile["historyId"]), tokens=refreshed)


# ---------------------------------------------------------------- send (gateway-only)


def build_mime(
    *,
    from_address: str,
    to: list[str],
    cc: list[str],
    subject: str,
    body_text: str,
    body_html: str,
    in_reply_to: str,
) -> bytes:
    mime = MimeMessage()
    mime["From"] = from_address
    mime["To"] = ", ".join(to)
    if cc:
        mime["Cc"] = ", ".join(cc)
    mime["Subject"] = subject
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to
    mime.set_content(body_text)
    if body_html:
        mime.add_alternative(body_html, subtype="html")
    return mime.as_bytes()


def _provider_send_gmail(
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
    """The Gmail send call. Never call this directly — go through send_via_provider."""
    raw = base64.urlsafe_b64encode(
        build_mime(
            from_address=from_address,
            to=to,
            cc=cc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            in_reply_to=in_reply_to,
        )
    ).decode()
    body: dict[str, Any] = {"raw": raw}
    if provider_thread_id:
        body["threadId"] = provider_thread_id
    sent = service(tokens).users().messages().send(userId="me", body=body).execute()
    return str(sent["id"])
