"""Base model and tenant scoping shared by every app. PROJECT_SPECS §12."""

import uuid
from typing import TYPE_CHECKING, Self

from django.db import models

if TYPE_CHECKING:
    from apps.accounts.models import Organization


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class TenantQuerySet(models.QuerySet):  # type: ignore[type-arg]
    def for_org(self, org: "Organization") -> Self:
        return self.filter(org=org)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """`Model.objects.for_org(org)` is the only sanctioned read of tenant data."""


class TenantModel(BaseModel):
    org = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="+")
    objects = TenantManager()

    class Meta(BaseModel.Meta):
        abstract = True


class AppendOnlyMixin(models.Model):
    """Rows may be created, never updated or deleted."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not self._state.adding:
            raise ValueError(f"{type(self).__name__} is append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise ValueError(f"{type(self).__name__} is append-only")
