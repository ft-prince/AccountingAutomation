import pytest


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):  # type: ignore[no-untyped-def]
    """In-memory object store: no MinIO in unit tests."""
    blobs: dict[str, bytes] = {}
    from apps.documents import storage

    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: blobs.__setitem__(key, data))
    monkeypatch.setattr(storage, "get_object", lambda key: blobs[key])
    return blobs


@pytest.fixture
def pdf_bytes() -> bytes:
    import io

    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()
