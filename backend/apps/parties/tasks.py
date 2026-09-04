"""Celery entry points. Idempotent; take IDs, not objects."""

import logging

from celery import shared_task

from apps.accounts.models import AATOBracket
from apps.core.audit import record
from apps.parties.models import AATOSource, Party

log = logging.getLogger(__name__)

# PROJECT_SPECS §3.5: e-invoicing is mandatory above ₹5 crore AATO, so a supplier
# who issued an IRN is demonstrably in scope — at least the 5–10 crore bracket.
IRN_IMPLIED_BRACKET = AATOBracket.FROM_5_TO_10CR
# Ordered low → high; a party's bracket is only ever raised, never lowered.
BRACKET_RANK: dict[str, int] = {
    AATOBracket.BELOW_5CR: 0,
    AATOBracket.FROM_5_TO_10CR: 1,
    AATOBracket.ABOVE_10CR: 2,
}


def _human_set(party: Party) -> bool:
    """A human typed this bracket: manual source and something other than the default."""
    return party.aato_source == AATOSource.MANUAL and party.aato_bracket != AATOBracket.BELOW_5CR


@shared_task
def infer_vendor_aato() -> dict[str, int]:
    """Raise vendor AATO brackets from e-invoice evidence. Safe to run repeatedly."""
    from apps.invoices.models import Direction, Invoice, InvoiceStatus

    party_ids = (
        Invoice.objects.filter(status=InvoiceStatus.CONFIRMED, direction=Direction.INWARD)
        .exclude(irn="")
        .values_list("party_id", flat=True)
        .distinct()
    )
    changed = skipped = 0
    for party in Party.objects.filter(pk__in=list(party_ids)).select_related("org"):
        if (
            _human_set(party)
            or BRACKET_RANK[party.aato_bracket] >= BRACKET_RANK[IRN_IMPLIED_BRACKET]
        ):
            skipped += 1
            continue
        before = {"aato_bracket": party.aato_bracket, "aato_source": party.aato_source}
        party.aato_bracket = IRN_IMPLIED_BRACKET
        party.aato_source = AATOSource.INFERRED
        party.save(update_fields=["aato_bracket", "aato_source", "updated_at"])
        record(
            party.org,
            actor=None,
            entity=party,
            action="party.aato.inferred",
            before=before,
            after={"aato_bracket": party.aato_bracket, "aato_source": party.aato_source},
        )
        changed += 1
    log.info("infer_vendor_aato: %s raised, %s left alone", changed, skipped)
    return {"changed": changed, "skipped": skipped}
