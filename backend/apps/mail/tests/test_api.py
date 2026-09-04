"""OAuth connect/callback/revoke/grant-send-scope, mailboxes, threads, style guide, templates.
Roles per §4/§12: connect + style guide are owner-only; viewer changes nothing; cross-org is 404."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role
from apps.core.audit import AuditEvent
from apps.mail.crypto import decrypt_tokens
from apps.mail.factories import MailboxFactory, MessageFactory, ThreadFactory
from apps.mail.models import MailboxConnection, ThreadStatus
from apps.mail.providers import gmail, graph
from apps.mail.services.oauth import SESSION_KEY
from apps.parties.factories import PartyFactory
from conftest import client_for

pytestmark = pytest.mark.django_db

SECRET = "1//refresh-secret"


@pytest.fixture
def google(monkeypatch):  # type: ignore[no-untyped-def]
    """Stub the pieces of google-auth-oauthlib that need the network."""
    seen: dict[str, object] = {}

    def auth_url(scopes, *, state, redirect_uri):  # type: ignore[no-untyped-def]
        seen.update(scopes=scopes, state=state, redirect_uri=redirect_uri)
        return f"https://accounts.google.com/o/oauth2/auth?state={state}", "verifier-abc"

    def exchange(code, *, scopes, redirect_uri, code_verifier=""):  # type: ignore[no-untyped-def]
        assert code == "the-code"
        # Google rejects the exchange without the PKCE verifier from the authorize step.
        seen.update(code_verifier=code_verifier)
        return {"token": "at", "refresh_token": SECRET, "scopes": scopes}

    monkeypatch.setattr(gmail, "authorization_url", auth_url)
    monkeypatch.setattr(gmail, "exchange_code", exchange)
    monkeypatch.setattr(gmail, "profile_email", lambda tokens: "Accounts@nexren.example")
    monkeypatch.setattr(gmail, "revoke", lambda tokens: True)
    return seen


def connect_gmail(client, google):  # type: ignore[no-untyped-def]
    resp = client.post("/api/mail/connect/gmail")
    assert resp.status_code == 200, resp.content
    state = google["state"]
    resp = client.get(f"/api/mail/connect/gmail/callback?code=the-code&state={state}")
    assert resp.status_code == 201, resp.content
    return MailboxConnection.objects.get(pk=resp.json()["id"])


def test_owner_connects_gmail_and_tokens_are_encrypted(client_a, org_a, google) -> None:  # type: ignore[no-untyped-def]
    resp = client_a.post("/api/mail/connect/gmail")
    assert resp.status_code == 200
    assert resp.json()["authorization_url"].startswith("https://accounts.google.com/")
    assert client_a.session[SESSION_KEY]["state"] == google["state"]
    assert google["redirect_uri"] == "http://testserver/api/mail/connect/gmail/callback"
    assert google["scopes"] == gmail.READ_SCOPES  # read scopes only in Phase 14
    mailbox = connect_gmail(client_a, google)
    assert mailbox.org == org_a.org and mailbox.email_address == "accounts@nexren.example"
    assert mailbox.connected_by == org_a.user and mailbox.has_send_scope is False
    assert SECRET not in mailbox.encrypted_tokens
    assert decrypt_tokens(mailbox.encrypted_tokens)["refresh_token"] == SECRET
    assert AuditEvent.objects.filter(entity_id=mailbox.pk, action="mailbox.connect").exists()
    assert SESSION_KEY not in client_a.session
    # reconnecting the same address updates the row instead of duplicating it
    connect_gmail(client_a, google)
    assert MailboxConnection.objects.for_org(org_a.org).count() == 1


def test_viewer_and_accountant_cannot_connect(org_a, viewer_client) -> None:  # type: ignore[no-untyped-def]
    assert viewer_client.post("/api/mail/connect/gmail").status_code == 403
    accountant = client_for(MembershipFactory(org=org_a.org, role=Role.ACCOUNTANT))
    assert accountant.post("/api/mail/connect/gmail").status_code == 403
    assert viewer_client.get("/api/mail/mailboxes/").status_code == 200


def test_callback_rejects_bad_state_missing_flow_and_provider_error(client_a, google) -> None:  # type: ignore[no-untyped-def]
    assert client_a.get("/api/mail/connect/gmail/callback?code=x&state=y").status_code == 400
    client_a.post("/api/mail/connect/gmail")
    assert client_a.get("/api/mail/connect/gmail/callback?code=x&state=wrong").status_code == 400
    client_a.post("/api/mail/connect/gmail")
    resp = client_a.get(
        f"/api/mail/connect/gmail/callback?error=access_denied&state={google['state']}"
    )
    assert resp.status_code == 400 and "access_denied" in resp.json()["detail"]
    assert client_a.post("/api/mail/connect/yahoo").status_code == 400
    assert client_a.post("/api/mail/mailboxes/").status_code == 400


def test_unconfigured_oauth_is_a_400_not_a_crash(client_a, settings) -> None:  # type: ignore[no-untyped-def]
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    assert client_a.post("/api/mail/connect/gmail").status_code == 400
    settings.GOOGLE_OAUTH_CLIENT_ID = "x"
    settings.OAUTH_REDIRECT_BASE = ""
    assert client_a.post("/api/mail/connect/gmail").status_code == 400


def test_microsoft_connect_flow(client_a, org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        graph,
        "initiate_flow",
        lambda scopes, *, state, redirect_uri: {
            "auth_uri": f"https://login.microsoftonline.com/?state={state}",
            "state": state,
            "scope": scopes,
        },
    )
    monkeypatch.setattr(
        graph,
        "exchange_flow",
        lambda flow, query: {
            "access_token": "a",
            "refresh_token": SECRET,
            "scopes": ["Mail.Read", "User.Read"],
            "email": "Ops@contoso.example",
        },
    )
    resp = client_a.post("/api/mail/connect/microsoft")
    assert resp.status_code == 200
    state = client_a.session[SESSION_KEY]["state"]
    resp = client_a.get(f"/api/mail/connect/microsoft/callback?code=c&state={state}")
    assert resp.status_code == 201
    mailbox = MailboxConnection.objects.get(org=org_a.org, provider="microsoft")
    assert mailbox.email_address == "ops@contoso.example" and mailbox.scopes == [
        "Mail.Read",
        "User.Read",
    ]


def test_grant_send_scope_second_consent(client_a, org_a, google) -> None:  # type: ignore[no-untyped-def]
    mailbox = connect_gmail(client_a, google)
    resp = client_a.post(f"/api/mail/mailboxes/{mailbox.pk}/grant-send-scope/")
    assert resp.status_code == 200
    assert gmail.SEND_SCOPE in google["scopes"] and gmail.READONLY_SCOPE in google["scopes"]
    resp = client_a.get(f"/api/mail/connect/gmail/callback?code=the-code&state={google['state']}")
    assert resp.status_code == 201
    mailbox.refresh_from_db()
    assert mailbox.has_send_scope is True and mailbox.needs_send_scope is False
    assert MailboxConnection.objects.for_org(org_a.org).count() == 1


def test_grant_send_scope_rejects_a_different_mailbox(client_a, google, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mailbox = connect_gmail(client_a, google)
    client_a.post(f"/api/mail/mailboxes/{mailbox.pk}/grant-send-scope/")
    monkeypatch.setattr(gmail, "profile_email", lambda tokens: "someone-else@nexren.example")
    resp = client_a.get(f"/api/mail/connect/gmail/callback?code=the-code&state={google['state']}")
    assert resp.status_code == 400
    mailbox.refresh_from_db()
    assert mailbox.has_send_scope is False


def test_revoke_clears_tokens_and_is_owner_only(client_a, viewer_client, client_b, google) -> None:  # type: ignore[no-untyped-def]
    mailbox = connect_gmail(client_a, google)
    assert viewer_client.post(f"/api/mail/mailboxes/{mailbox.pk}/revoke/").status_code == 403
    assert client_b.post(f"/api/mail/mailboxes/{mailbox.pk}/revoke/").status_code == 404
    resp = client_a.post(f"/api/mail/mailboxes/{mailbox.pk}/revoke/")
    assert resp.status_code == 200 and resp.json()["status"] == "revoked"
    mailbox.refresh_from_db()
    assert mailbox.encrypted_tokens == "" and mailbox.scopes == []
    event = AuditEvent.objects.get(entity_id=mailbox.pk, action="mailbox.revoke")
    assert event.after["revoked_remotely"] is True


def test_revoke_survives_provider_failure(client_a, google, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mailbox = connect_gmail(client_a, google)

    def boom(tokens):  # type: ignore[no-untyped-def]
        raise RuntimeError("network")

    monkeypatch.setattr(gmail, "revoke", boom)
    assert client_a.post(f"/api/mail/mailboxes/{mailbox.pk}/revoke/").status_code == 200
    mailbox.refresh_from_db()
    assert mailbox.status == "revoked" and mailbox.encrypted_tokens == ""


def test_mailbox_list_is_org_scoped_and_hides_tokens(client_a, client_b, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    mine = MailboxFactory(org=org_a.org)
    MailboxFactory(org=org_b.org)
    body = client_a.get("/api/mail/mailboxes/").json()
    assert [m["id"] for m in body["results"]] == [str(mine.pk)]
    assert "encrypted_tokens" not in body["results"][0]
    assert client_b.get(f"/api/mail/mailboxes/{mine.pk}/").status_code == 404


# ---------------------------------------------------------------- threads


def test_threads_list_filters_detail_and_cross_org_404(client_a, client_b, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_a.org)
    t1 = ThreadFactory(org=org_a.org, intent="dispute", status="new", party=party)
    t2 = ThreadFactory(org=org_a.org, intent="invoice_query", status="closed")
    MessageFactory(thread=t1)
    ThreadFactory(org=org_b.org, intent="dispute")
    ids = lambda r: {t["id"] for t in r.json()["results"]}  # noqa: E731
    assert ids(client_a.get("/api/mail/threads/")) == {str(t1.pk), str(t2.pk)}
    assert ids(client_a.get("/api/mail/threads/?intent=dispute")) == {str(t1.pk)}
    assert ids(client_a.get("/api/mail/threads/?status=closed")) == {str(t2.pk)}
    assert ids(client_a.get(f"/api/mail/threads/?party={party.pk}")) == {str(t1.pk)}
    detail = client_a.get(f"/api/mail/threads/{t1.pk}/")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 1 and detail.json()["drafts"] == []
    assert detail.json()["party_name"] == party.legal_name
    assert client_b.get(f"/api/mail/threads/{t1.pk}/").status_code == 404
    assert client_b.post(f"/api/mail/threads/{t1.pk}/ignore/").status_code == 404


def test_thread_actions_ignore_close_snooze_and_roles(client_a, viewer_client, org_a) -> None:  # type: ignore[no-untyped-def]
    thread = ThreadFactory(org=org_a.org)
    assert viewer_client.post(f"/api/mail/threads/{thread.pk}/ignore/").status_code == 403
    reviewer = client_for(MembershipFactory(org=org_a.org, role=Role.REVIEWER))
    assert reviewer.post(f"/api/mail/threads/{thread.pk}/ignore/").json()["status"] == "ignored"
    assert client_a.post(f"/api/mail/threads/{thread.pk}/close/").json()["status"] == "closed"
    past = (timezone.now() - timedelta(hours=1)).isoformat()
    assert (
        client_a.post(f"/api/mail/threads/{thread.pk}/snooze/", {"until": past}).status_code == 400
    )
    future = (timezone.now() + timedelta(days=1)).isoformat()
    resp = client_a.post(f"/api/mail/threads/{thread.pk}/snooze/", {"until": future})
    assert resp.status_code == 200 and resp.json()["snoozed_until"] is not None
    thread.refresh_from_db()
    assert thread.status == ThreadStatus.CLOSED
    assert AuditEvent.objects.filter(entity_id=thread.pk).count() == 3


# ---------------------------------------------------------------- style guide + templates


def test_style_guide_get_put_and_roles(client_a, viewer_client, org_a, client_b) -> None:  # type: ignore[no-untyped-def]
    assert client_a.get("/api/mail/style-guide").json()["sign_off"] == ""
    body = {
        "sign_off": "Warm regards,\nAccounts, Nexren AI",
        "tone_rules": "Short sentences. No exclamation marks.",
        "banned_phrases": ["kindly do the needful"],
        "must_include": ["GSTIN"],
        "few_shot_examples": [{"intent": "invoice_query", "body": "Dear Sir, ..."}],
    }
    resp = client_a.put("/api/mail/style-guide", body, format="json")
    assert resp.status_code == 200 and resp.json()["banned_phrases"] == ["kindly do the needful"]
    assert viewer_client.put("/api/mail/style-guide", body, format="json").status_code == 403
    accountant = client_for(MembershipFactory(org=org_a.org, role=Role.ACCOUNTANT))
    assert accountant.put("/api/mail/style-guide", body, format="json").status_code == 403
    too_many = {**body, "few_shot_examples": [{"body": "x"}] * 21}
    assert client_a.put("/api/mail/style-guide", too_many, format="json").status_code == 400
    bad = {**body, "few_shot_examples": ["not a dict"]}
    assert client_a.put("/api/mail/style-guide", bad, format="json").status_code == 400
    assert client_b.get("/api/mail/style-guide").json()["sign_off"] == ""  # org B has its own


def test_templates_list_and_create(client_a, client_b, viewer_client) -> None:  # type: ignore[no-untyped-def]
    body = {"intent": "statement_request", "name": "Statement", "body": "Dear {{name}}, attached."}
    assert viewer_client.post("/api/mail/templates/", body).status_code == 403
    assert client_a.post("/api/mail/templates/", body).status_code == 201
    assert client_a.get("/api/mail/templates/").json()["results"][0]["name"] == "Statement"
    assert client_a.get("/api/mail/templates/?intent=dispute").json()["results"] == []
    assert client_b.get("/api/mail/templates/").json()["results"] == []


@pytest.mark.django_db
def test_gmail_pkce_verifier_survives_the_round_trip(client_a, google) -> None:  # type: ignore[no-untyped-def]
    """Regression: the verifier is generated while building the authorize URL, so it must be
    carried in the session to the token exchange or Google answers "Missing code verifier"."""
    connect_gmail(client_a, google)
    assert google["code_verifier"] == "verifier-abc"


@pytest.mark.django_db
def test_provider_failure_becomes_a_readable_message_not_a_traceback(client_a, google) -> None:  # type: ignore[no-untyped-def]
    """A disabled Gmail API used to surface as a raw 500 HttpError page."""
    from apps.mail.providers import gmail as gmail_provider

    def boom(tokens):  # type: ignore[no-untyped-def]
        raise RuntimeError(
            "<HttpError 403 ... 'reason': 'accessNotConfigured', "
            "Gmail API has not been used in project 451364275103 before or it is disabled.>"
        )

    client_a.post("/api/mail/connect/gmail")
    gmail_provider.profile_email = boom  # type: ignore[assignment]
    try:
        resp = client_a.get(
            f"/api/mail/connect/gmail/callback?code=the-code&state={google['state']}"
        )
    finally:
        pass
    assert resp.status_code == 400, resp.content[:200]
    detail = str(resp.json())
    assert "Gmail API is not enabled" in detail and "451364275103" not in detail
