"""Mailbox tokens encrypted at rest with Fernet (PROJECT_SPECS §12).
`cryptography.fernet` is used directly: django-fernet-fields (named in §2) is unmaintained."""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class TokenCryptoError(ValueError):
    pass


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_tokens(tokens: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(tokens).encode()).decode()


def decrypt_tokens(blob: str) -> dict[str, Any]:
    if not blob:
        raise TokenCryptoError("mailbox has no stored credentials")
    try:
        data = json.loads(_fernet().decrypt(blob.encode()))
    except (InvalidToken, ValueError) as exc:
        raise TokenCryptoError("stored credentials cannot be decrypted") from exc
    if not isinstance(data, dict):
        raise TokenCryptoError("stored credentials are malformed")
    return data
