"""GET /api/mail/setup-status — the OAuth preflight checklist. PROJECT_SPECS §6.3, §12."""

import pytest
from django.test import override_settings

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role
from apps.mail.models import MailboxConnection, Provider
from apps.mail.services import oauth
from conftest import client_for

pytestmark = pytest.mark.django_db

URL = "/api/mail/setup-status"
CONFIGURED = {
    "GOOGLE_OAUTH_CLIENT_ID": "gid",
    "GOOGLE_OAUTH_CLIENT_SECRET": "gsecret",
    "MICROSOFT_OAUTH_CLIENT_ID": "mid",
    "MICROSOFT_OAUTH_CLIENT_SECRET": "msecret",
    "OAUTH_REDIRECT_BASE": "https://app.nexren.ai",
}


def _by_provider(body):  # type: ignore[no-untyped-def]
    return {p["provider"]: p for p in body["providers"]}


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="",
    GOOGLE_OAUTH_CLIENT_SECRET="",
    MICROSOFT_OAUTH_CLIENT_ID="mid",
    MICROSOFT_OAUTH_CLIENT_SECRET="",
    OAUTH_REDIRECT_BASE="",
)
def test_missing_credentials_are_named_per_provider(client_a) -> None:  # type: ignore[no-untyped-def]
    body = client_a.get(URL).json()

    providers = _by_provider(body)
    assert providers["gmail"]["configured"] is False
    assert providers["gmail"]["missing_env"] == [
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "OAUTH_REDIRECT_BASE",
    ]
    assert providers["microsoft"]["missing_env"] == [
        "MICROSOFT_OAUTH_CLIENT_SECRET",
        "OAUTH_REDIRECT_BASE",
    ]
    assert providers["gmail"]["redirect_uri"] == ""


@override_settings(**CONFIGURED)
def test_fully_configured_reports_no_missing_env(client_a) -> None:  # type: ignore[no-untyped-def]
    providers = _by_provider(client_a.get(URL).json())

    assert [p["configured"] for p in providers.values()] == [True, True]
    assert [p["missing_env"] for p in providers.values()] == [[], []]


@override_settings(**CONFIGURED)
def test_redirect_uri_is_the_one_the_oauth_service_uses(client_a) -> None:  # type: ignore[no-untyped-def]
    providers = _by_provider(client_a.get(URL).json())

    for provider in Provider.values:
        assert providers[provider]["redirect_uri"] == oauth._redirect_uri(provider)  # noqa: SLF001
    assert providers["gmail"]["redirect_uri"] == (
        "https://app.nexren.ai/api/mail/connect/gmail/callback"
    )


@override_settings(**CONFIGURED)
def test_scopes_match_the_oauth_service(client_a) -> None:  # type: ignore[no-untyped-def]
    providers = _by_provider(client_a.get(URL).json())

    for provider in Provider.values:
        assert providers[provider]["read_scopes"] == oauth.read_scopes(provider)
        assert providers[provider]["send_scope"] == oauth.send_scope(provider)
    assert "gmail.send" in providers["gmail"]["send_scope"]


@override_settings(**CONFIGURED)
def test_no_secret_value_is_ever_echoed(client_a) -> None:  # type: ignore[no-untyped-def]
    raw = client_a.get(URL).content.decode()

    assert "gsecret" not in raw
    assert "msecret" not in raw
    assert "gid" not in raw


@override_settings(**CONFIGURED)
def test_mailboxes_are_listed_with_send_scope_state(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    MailboxConnection.objects.create(
        org=org_a.org,
        provider=Provider.GMAIL,
        email_address="ops@nexren.ai",
        scopes=oauth.read_scopes(Provider.GMAIL),
        needs_send_scope=True,
    )

    mailboxes = client_a.get(URL).json()["mailboxes"]

    assert len(mailboxes) == 1
    assert mailboxes[0]["email_address"] == "ops@nexren.ai"
    assert mailboxes[0]["status"] == "active"
    assert mailboxes[0]["has_send_scope"] is False
    assert mailboxes[0]["needs_send_scope"] is True


@override_settings(**CONFIGURED)
def test_org_b_mailboxes_are_invisible_to_org_a(client_a, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    MailboxConnection.objects.create(
        org=org_b.org, provider=Provider.GMAIL, email_address="theirs@example.com"
    )
    MailboxConnection.objects.create(
        org=org_a.org, provider=Provider.GMAIL, email_address="ours@nexren.ai"
    )

    mailboxes = client_a.get(URL).json()["mailboxes"]

    assert [m["email_address"] for m in mailboxes] == ["ours@nexren.ai"]


@override_settings(**CONFIGURED)
@pytest.mark.parametrize("role", [Role.ACCOUNTANT, Role.VIEWER])
def test_non_owner_is_forbidden(org_a, role) -> None:  # type: ignore[no-untyped-def]
    client = client_for(MembershipFactory(org=org_a.org, role=role))

    assert client.get(URL).status_code == 403
