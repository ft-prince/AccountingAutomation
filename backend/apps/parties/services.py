"""Party merge with a handler registry that later phases append to. PROJECT_SPECS §4."""

from collections.abc import Callable
from typing import Any

from django.db import transaction

from apps.core.audit import record
from apps.parties.models import Party

MergeHandler = Callable[[Party, Party], None]
# Each handler reassigns one entity type from source → target. Phase 7 invoices,
# Phase 8 payments, Phase 14 threads register here.
party_merge_handlers: list[MergeHandler] = []


def register_merge_handler(fn: MergeHandler) -> MergeHandler:
    party_merge_handlers.append(fn)
    return fn


class MergeError(ValueError):
    pass


def merge_party(source: Party, target: Party, *, actor: Any) -> Party:
    if source.pk == target.pk:
        raise MergeError("Cannot merge a party into itself.")
    if source.org_id != target.org_id:
        raise MergeError("Parties belong to different organisations.")
    if target.merged_into_id is not None:
        raise MergeError("Target has itself been merged.")
    with transaction.atomic():
        for handler in party_merge_handlers:
            handler(source, target)
        before = {"merged_into": None, "is_active": source.is_active}
        source.merged_into = target
        source.is_active = False
        source.save(update_fields=["merged_into", "is_active", "updated_at"])
        record(
            source.org,
            actor=actor,
            entity=source,
            action="party.merge",
            before=before,
            after={"merged_into": str(target.pk), "is_active": False},
        )
    return target
