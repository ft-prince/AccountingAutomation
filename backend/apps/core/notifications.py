"""In-app notifications and backup bookkeeping. PROJECT_SPECS §12.

Notifications are IN-APP ONLY. Nothing here sends email: outbound mail has exactly one
gateway (mail/services.send_via_provider) and it requires a human reviewer or a
configured report schedule (CLAUDE.md §4, PROJECT_SPECS §7.3).
"""

import uuid
from typing import Any

from django.db import models, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.api import HasOrg, OrgScopedViewSet, current_org
from apps.core.models import BaseModel, TenantModel

CODE_MAX_LENGTH = 60
DEDUPE_KEY_MAX_LENGTH = 200


class Level(models.TextChoices):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


class Notification(TenantModel):
    """One org-scoped alert. `dedupe_key` keeps a nightly check from piling up duplicates."""

    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    code = models.CharField(max_length=CODE_MAX_LENGTH)  # stable slug, e.g. "backup.failed"
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=DEDUPE_KEY_MAX_LENGTH, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        indexes = [models.Index(fields=["org", "read_at", "dismissed_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "dedupe_key"],
                condition=models.Q(read_at__isnull=True, dismissed_at__isnull=True),
                name="uq_notification_open_dedupe",
            )
        ]

    @property
    def is_open(self) -> bool:
        return self.read_at is None and self.dismissed_at is None

    def __str__(self) -> str:
        return f"{self.level}:{self.code}"


class BackupRun(BaseModel):
    """One pg_dump attempt. Org-agnostic: the dump is the whole database."""

    objects: "models.Manager[BackupRun]" = models.Manager()

    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    size_bytes = models.BigIntegerField(default=0)
    object_key = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"backup {'ok' if self.ok else 'failed'} {self.started_at:%Y-%m-%dT%H:%M:%SZ}"


def _open_qs(org: Any, dedupe_key: str) -> models.QuerySet[Notification]:
    return Notification.objects.for_org(org).filter(
        dedupe_key=dedupe_key, read_at__isnull=True, dismissed_at__isnull=True
    )


def notify(
    org: Any,
    *,
    level: str,
    code: str,
    title: str,
    body: str = "",
    dedupe_key: str | None = None,
    entity: Any = None,
) -> Notification:
    """Create the notification, or refresh the open one carrying the same dedupe key."""
    entity_type = type(entity).__name__ if entity is not None else ""
    entity_id: uuid.UUID | None = getattr(entity, "pk", None) if entity is not None else None
    fields: dict[str, Any] = {
        "level": level,
        "code": code,
        "title": title,
        "body": body,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "dedupe_key": dedupe_key or "",
    }
    with transaction.atomic():
        if dedupe_key:
            existing = _open_qs(org, dedupe_key).select_for_update().first()
            if existing is not None:
                for name, value in fields.items():
                    setattr(existing, name, value)
                existing.save(update_fields=[*fields, "updated_at"])
                return existing
        return Notification.objects.create(org=org, **fields)


def resolve(org: Any, dedupe_key: str) -> int:
    """The condition cleared: dismiss the open notification so a fix silences its own alarm."""
    if not dedupe_key:
        return 0
    return int(_open_qs(org, dedupe_key).update(dismissed_at=timezone.now()))


class NotificationSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    class Meta:
        model = Notification
        fields = [
            "id",
            "level",
            "code",
            "title",
            "body",
            "entity_type",
            "entity_id",
            "dedupe_key",
            "read_at",
            "dismissed_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationViewSet(OrgScopedViewSet):
    """GET /api/notifications/?unread=1 plus read / dismiss / read-all. Any member may act."""

    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()  # type: ignore[no-untyped-call]
        if self.action in ("read", "dismiss"):
            return qs
        if self.request.query_params.get("unread") in ("1", "true"):
            return qs.filter(read_at__isnull=True, dismissed_at__isnull=True)
        return qs.filter(dismissed_at__isnull=True)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise serializers.ValidationError("Notifications are raised by the system, not the API.")

    @action(detail=True, methods=["post"], permission_classes=[HasOrg])
    def read(self, request: Request, pk: str) -> Response:
        note = self.get_object()
        if note.read_at is None:
            note.read_at = timezone.now()
            note.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(note).data)

    @action(detail=True, methods=["post"], permission_classes=[HasOrg])
    def dismiss(self, request: Request, pk: str) -> Response:
        note = self.get_object()
        now = timezone.now()
        note.read_at = note.read_at or now
        note.dismissed_at = note.dismissed_at or now
        note.save(update_fields=["read_at", "dismissed_at", "updated_at"])
        return Response(NotificationSerializer(note).data)

    @action(detail=False, methods=["post"], url_path="read-all", permission_classes=[HasOrg])
    def read_all(self, request: Request) -> Response:
        n = (
            Notification.objects.for_org(current_org(request))
            .filter(read_at__isnull=True)
            .update(read_at=timezone.now())
        )
        return Response({"marked_read": n})
