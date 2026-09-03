"""JSON logs with request ids for production. PROJECT_SPECS Phase 19."""

import json
import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from django.http import HttpRequest, HttpResponse

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id.set(rid)
        try:
            response = self.get_response(request)
        finally:
            request_id.reset(token)
        response["X-Request-ID"] = rid
        return response


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("document_id", "task"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)
