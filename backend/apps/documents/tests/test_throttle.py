import pytest

pytestmark = pytest.mark.django_db


def test_upload_throttle_is_per_org(client_a, settings) -> None:  # type: ignore[no-untyped-def]
    from django.core.cache import cache

    cache.clear()
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "upload": "2/hour",
        },
    }
    from rest_framework.settings import api_settings

    api_settings.reload()
    from django.core.files.uploadedfile import SimpleUploadedFile

    codes = [
        client_a.post(
            "/api/documents/", {"file": SimpleUploadedFile(f"{i}.pdf", b"%PDF-bad" + bytes([i]))}
        ).status_code
        for i in range(3)
    ]
    api_settings.reload()
    assert codes[-1] == 429
