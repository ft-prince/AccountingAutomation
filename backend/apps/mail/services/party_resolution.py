"""Party resolution for a thread. PROJECT_SPECS §6.5 step 1:
sender address == Party.primary_email → sender domain ∈ Party.email_domains →
GSTIN or invoice numbers found in the text → unresolved (None)."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from django.db.models.functions import Upper

from apps.invoices.models import Invoice
from apps.mail.domain.text import find_gstins, find_invoice_numbers
from apps.mail.models import EmailThread
from apps.parties.models import Party
from apps.parties.services import register_merge_handler

BY_PRIMARY_EMAIL = "primary_email"
BY_DOMAIN = "email_domain"
BY_GSTIN = "gstin"
BY_INVOICE_NUMBER = "invoice_number"
UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Resolution:
    party: Party | None
    how: str
    invoice_ids: list[uuid.UUID] = field(default_factory=list)


def _live_parties(org: Any) -> Any:
    return Party.objects.for_org(org).filter(merged_into__isnull=True, is_active=True)


def _invoices_mentioned(org: Any, text: str) -> list[Invoice]:
    tokens = find_invoice_numbers(text)
    if not tokens:
        return []
    return list(
        Invoice.objects.for_org(org)
        .annotate(number_upper=Upper("invoice_number"))
        .filter(number_upper__in=tokens)
        .select_related("party")
    )


def resolve_party(org: Any, *, sender: str, text: str) -> Resolution:
    sender = sender.strip().lower()
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
    invoices = _invoices_mentioned(org, text)
    party = _live_parties(org).filter(primary_email__iexact=sender).first() if sender else None
    how = BY_PRIMARY_EMAIL
    if party is None and domain:
        party = _live_parties(org).filter(email_domains__contains=[domain]).first()
        how = BY_DOMAIN
    if party is None:
        gstins = find_gstins(text)
        party = _live_parties(org).filter(gstin__in=gstins).first() if gstins else None
        how = BY_GSTIN
    if party is None:
        party = next((inv.party for inv in invoices if inv.party.merged_into_id is None), None)
        how = BY_INVOICE_NUMBER
    if party is None:
        return Resolution(party=None, how=UNRESOLVED, invoice_ids=[i.pk for i in invoices])
    linked = [i.pk for i in invoices if i.party_id == party.pk]
    return Resolution(party=party, how=how, invoice_ids=linked)


def apply_resolution(thread: EmailThread, *, sender: str, text: str) -> Resolution:
    resolution = resolve_party(thread.org, sender=sender, text=text)
    thread.party = resolution.party
    thread.party_resolution = resolution.how
    thread.linked_invoices = list(dict.fromkeys([*thread.linked_invoices, *resolution.invoice_ids]))
    thread.save(update_fields=["party", "party_resolution", "linked_invoices", "updated_at"])
    return resolution


@register_merge_handler
def _reassign_threads(source: Party, target: Party) -> None:
    EmailThread.objects.filter(party=source).update(party=target)
