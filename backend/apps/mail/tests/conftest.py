import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def mail_settings(settings):  # type: ignore[no-untyped-def]
    """A throwaway Fernet key and OAuth config so tests never depend on .env."""
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.OAUTH_REDIRECT_BASE = "http://testserver"
    settings.GOOGLE_OAUTH_CLIENT_ID = "test-google-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "test-google-client-secret"
    settings.MICROSOFT_OAUTH_CLIENT_ID = "test-ms-client-id"
    settings.MICROSOFT_OAUTH_CLIENT_SECRET = "test-ms-client-secret"
    settings.ANTHROPIC_API_KEY = "test-anthropic-key"
    return settings


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):  # type: ignore[no-untyped-def]
    """In-memory object store: no MinIO in unit tests (same shape as documents/tests)."""
    blobs: dict[str, bytes] = {}
    from apps.documents import storage

    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: blobs.__setitem__(key, data))
    monkeypatch.setattr(storage, "get_object", lambda key: blobs[key])
    return blobs
