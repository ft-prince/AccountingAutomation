"""AuditEvent — append-only. PROJECT_SPECS §4, §12."""

from typing import Any

from django.db import models

from apps.core.models import AppendOnlyMixin, TenantModel


class AuditEvent(AppendOnlyMixin, TenantModel):
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    entity_type = models.CharField(max_length=60)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=40)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        indexes = [models.Index(fields=["org", "entity_type", "entity_id"])]


def record(
    org: Any,
    *,
    actor: Any,
    entity: Any,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        org=org,
        actor=actor if actor is not None and actor.is_authenticated else None,
        entity_type=type(entity).__name__,
        entity_id=entity.pk,
        action=action,
        before=before,
        after=after,
    )
