"""API key issue/verify. Keys are 'nxf_' + 8-char prefix + 32 random chars; only sha256 stored."""

import hashlib
import secrets

from apps.accounts.models import APIKey


def issue(org, name: str, created_by) -> tuple[APIKey, str]:  # type: ignore[no-untyped-def]
    raw = "nxf_" + secrets.token_urlsafe(30)
    key = APIKey.objects.create(
        org=org,
        name=name[:100],
        prefix=raw[4:12],
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        created_by=created_by,
    )
    return key, raw


def verify(raw: str) -> APIKey | None:
    if not raw.startswith("nxf_"):
        return None
    return (
        APIKey.objects.filter(
            prefix=raw[4:12],
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            revoked_at__isnull=True,
        )
        .select_related("org")
        .first()
    )
