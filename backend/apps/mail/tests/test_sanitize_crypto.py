"""Token encryption at rest (§12) and inbound HTML sanitisation (§12)."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from apps.mail.crypto import TokenCryptoError, decrypt_tokens, encrypt_tokens
from apps.mail.factories import MailboxFactory
from apps.mail.models import MailboxConnection
from apps.mail.sanitize import html_to_text, sanitize_html

SECRET = "1//refresh-token-very-secret"


def test_encrypt_decrypt_round_trip(db) -> None:  # type: ignore[no-untyped-def]
    blob = encrypt_tokens({"token": "at", "refresh_token": SECRET})
    assert SECRET not in blob
    assert decrypt_tokens(blob) == {"token": "at", "refresh_token": SECRET}


def test_raw_token_never_appears_in_db_row(db) -> None:  # type: ignore[no-untyped-def]
    mailbox = MailboxFactory(encrypted_tokens=encrypt_tokens({"refresh_token": SECRET}))
    table = MailboxConnection._meta.db_table
    with connection.cursor() as cur:
        cur.execute(f"SELECT * FROM {table} WHERE id = %s", [str(mailbox.pk)])
        row = cur.fetchone()
    assert SECRET not in str(row)
    assert decrypt_tokens(mailbox.encrypted_tokens)["refresh_token"] == SECRET


def test_decrypt_rejects_empty_garbage_and_wrong_key(settings) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(TokenCryptoError):
        decrypt_tokens("")
    with pytest.raises(TokenCryptoError):
        decrypt_tokens("not-a-fernet-token")
    blob = encrypt_tokens({"a": 1})
    from cryptography.fernet import Fernet

    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    with pytest.raises(TokenCryptoError):
        decrypt_tokens(blob)


def test_missing_key_is_a_configuration_error(settings) -> None:  # type: ignore[no-untyped-def]
    settings.FIELD_ENCRYPTION_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        encrypt_tokens({"a": 1})


def test_sanitize_strips_script_style_iframe_and_tracking_pixel() -> None:
    html = (
        "<html><head><style>p{color:red}</style></head><body>"
        "<p>Invoice <b>INV-1</b> attached.</p>"
        "<script>alert('x')</script>"
        "<iframe src='https://evil.example'></iframe>"
        '<img src="https://track.example/pixel.gif?id=1" width="1" height="1">'
        '<a href="javascript:alert(1)">bad</a> <a href="https://ok.example">ok</a>'
        "<!-- comment --></body></html>"
    )
    out = sanitize_html(html)
    assert "<script" not in out and "alert" not in out
    assert "<style" not in out and "color:red" not in out
    assert "<iframe" not in out and "evil.example" not in out
    assert "<img" not in out and "pixel.gif" not in out
    assert "javascript:" not in out
    assert '<a href="https://ok.example">ok</a>' in out
    assert "<p>Invoice <b>INV-1</b> attached.</p>" in out
    assert "comment" not in out


def test_html_to_text_keeps_breaks_and_unescapes() -> None:
    html = "<div>Dear&nbsp;Sir,<br>Amount is &#8377;1,000</div><p>Regards</p><script>x()</script>"
    assert html_to_text(html) == "Dear Sir,\nAmount is ₹1,000\nRegards"
