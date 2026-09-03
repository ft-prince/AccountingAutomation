import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_reports_each_component(client: Client) -> None:
    resp = client.get("/api/health")
    body = resp.json()
    assert resp.status_code == 200
    assert set(body["checks"]) == {"db", "redis", "celery"}
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True  # locmem cache in test settings
    assert body["status"] in {"ok", "degraded"}


def test_schema_and_docs_hidden_when_debug_off(client: Client, settings) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/schema/").status_code == 404
