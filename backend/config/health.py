from typing import Any

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse

from config.celery import app as celery_app

CELERY_PING_TIMEOUT_S = 1.0


def _check(fn: Any) -> dict[str, Any]:
    try:
        fn()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 — a health check reports, never raises
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _db() -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT 1")


def _redis() -> None:
    cache.set("health", "1", 5)
    if cache.get("health") != "1":
        raise RuntimeError("cache round-trip failed")


def _celery() -> None:
    replies = celery_app.control.ping(timeout=CELERY_PING_TIMEOUT_S)
    if not replies:
        raise RuntimeError("no worker replied")


def health(request: HttpRequest) -> JsonResponse:
    checks = {"db": _check(_db), "redis": _check(_redis), "celery": _check(_celery)}
    return JsonResponse(
        {"status": "ok" if all(c["ok"] for c in checks.values()) else "degraded", "checks": checks}
    )
