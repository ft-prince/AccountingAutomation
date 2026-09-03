import pytest

pytestmark = pytest.mark.django_db


def test_upload_throttle_is_per_org(client_a, client_b, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from django.core.cache import cache
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.core.throttling import UploadThrottle

    cache.clear()
    monkeypatch.setattr(UploadThrottle, "THROTTLE_RATES", {"upload": "2/hour"})

    def post(client, i):  # type: ignore[no-untyped-def]
        return client.post(
            "/api/documents/", {"file": SimpleUploadedFile(f"{i}.pdf", b"%PDF-x" + bytes([i]))}
        ).status_code

    assert [post(client_a, i) for i in range(3)] == [201, 201, 429]
    assert post(client_b, 9) == 201  # a different org has its own bucket
