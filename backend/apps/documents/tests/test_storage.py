from botocore.exceptions import ClientError

from apps.documents import storage

# Bound at import time, before the autouse fake_storage fixture patches the module attribute.
real_put_object = storage.put_object


class _Client:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.puts: list[dict[str, object]] = []

    def put_object(self, **kw):  # type: ignore[no-untyped-def]
        if kw["Bucket"] not in self.buckets:
            raise ClientError({"Error": {"Code": "NoSuchBucket"}}, "PutObject")
        self.puts.append(kw)

    def create_bucket(self, *, Bucket):  # type: ignore[no-untyped-def]  # noqa: N803
        self.buckets.add(Bucket)


def test_put_object_creates_a_missing_bucket_once(monkeypatch, settings) -> None:  # type: ignore[no-untyped-def]
    settings.AWS_STORAGE_BUCKET_NAME = "docs"
    client = _Client()
    monkeypatch.setattr(storage, "_client", lambda: client)
    real_put_object("k", b"x", "text/plain")
    real_put_object("k2", b"y", "text/plain", bucket="backups")
    assert client.buckets == {"docs", "backups"}
    assert [p["Bucket"] for p in client.puts] == ["docs", "backups"]


def test_put_object_reraises_other_errors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class Denied(_Client):
        def put_object(self, **kw):  # type: ignore[no-untyped-def]
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")

    monkeypatch.setattr(storage, "_client", lambda: Denied())
    try:
        real_put_object("k", b"x", "text/plain")
    except ClientError as exc:
        assert exc.response["Error"]["Code"] == "AccessDenied"
    else:
        raise AssertionError("expected ClientError")
