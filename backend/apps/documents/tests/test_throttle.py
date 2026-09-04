import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.throttling import UploadThrottle

pytestmark = pytest.mark.django_db


def test_upload_throttle_is_per_org(client_a, client_b, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cache.clear()
    monkeypatch.setattr(UploadThrottle, "THROTTLE_RATES", {"upload": "2/hour"})
    codes = [
        client_a.post(
            "/api/documents/",
            {"file": SimpleUploadedFile(f"{i}.pdf", b"%PDF-1.4 " + bytes([48 + i]))},
        ).status_code
        for i in range(3)
    ]
    assert codes == [201, 201, 429]
    # a different org has its own bucket
    r = client_b.post("/api/documents/", {"file": SimpleUploadedFile("b.pdf", b"%PDF-1.4 b")})
    assert r.status_code == 201
