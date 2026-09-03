"""Auto-match bank transactions to invoices. PROJECT_SPECS Phase 8 rules.
Credits → outward (customer) invoices only; debits → inward (vendor) invoices only."""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations
from typing import Any

from django.db import transaction
from django.db.models import F

from apps.core.audit import record
from apps.invoices.models import Invoice, InvoiceStatus, PaymentStatus
from apps.payments.models import BankTransaction, MatchStatus, Payment, PaymentDirection
from apps.payments.services.allocation import allocate

AMOUNT_TOLERANCE = Decimal("1.00")
DATE_WINDOW_DAYS = 10
AUTO_ACCEPT_SCORE = Decimal("0.80")
AUTO_ACCEPT_MARGIN = Decimal("0.15")
STOPWORDS = {
    "pvt",
    "ltd",
    "private",
    "limited",
    "llp",
    "inc",
    "co",
    "the",
    "and",
    "of",
    "india",
    "services",
    "solutions",
    "technologies",
}
_TOKEN = re.compile(r"[a-z0-9]{3,}")


@dataclass
class Candidate:
    invoices: list[Invoice]
    score: Decimal
    reasons: list[str] = field(default_factory=list)

    @property
    def amount(self) -> Decimal:
        return sum((i.total - i.amount_paid for i in self.invoices), Decimal("0"))


def _tokens(s: str) -> set[str]:
    return {t for t in _TOKEN.findall(s.lower()) if t not in STOPWORDS}


def _open_invoices(org: Any, direction: str) -> list[Invoice]:
    return list(
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED, direction=direction)
        .exclude(payment_status__in=[PaymentStatus.PAID, PaymentStatus.WRITTEN_OFF])
        .filter(total__gt=F("amount_paid"))
        .select_related("party")
    )


def _score(
    txn: BankTransaction, invoices: list[Invoice], amount_score: Decimal, amount_reason: str
) -> Candidate:
    score, reasons = amount_score, [amount_reason]
    desc = txn.description.lower()
    party = invoices[0].party
    party_tokens = _tokens(party.legal_name) | _tokens(party.display_name)
    if party_tokens & _tokens(desc):
        score += Decimal("0.30")
        reasons.append("party name in description")
    refs = {txn.reference.lower()} | {
        t for t in _tokens(txn.description) if any(c.isdigit() for c in t)
    }
    refs.discard("")
    for inv in invoices:
        note_tokens = _tokens(inv.notes) | {inv.invoice_number.lower()}
        if refs & note_tokens:
            score += Decimal("0.40")
            reasons.append("reference matches invoice notes/number")
            break
    for inv in invoices:
        anchor = inv.due_date or inv.invoice_date
        if abs((txn.date - anchor).days) <= DATE_WINDOW_DAYS:
            score += Decimal("0.10")
            reasons.append(f"within {DATE_WINDOW_DAYS} days of due date")
            break
    return Candidate(invoices, min(score, Decimal("1")), reasons)


def candidates_for(txn: BankTransaction) -> list[Candidate]:
    org = txn.bank_account.org
    direction = "outward" if txn.amount > 0 else "inward"
    target = abs(txn.amount)
    open_invs = _open_invoices(org, direction)
    out: list[Candidate] = []
    for inv in open_invs:
        outstanding = inv.total - inv.amount_paid
        if outstanding == target:
            out.append(_score(txn, [inv], Decimal("0.50"), "exact amount"))
        elif abs(outstanding - target) <= AMOUNT_TOLERANCE:
            out.append(_score(txn, [inv], Decimal("0.40"), "amount within ₹1"))
    by_party: dict[Any, list[Invoice]] = {}
    for inv in open_invs:
        by_party.setdefault(inv.party_id, []).append(inv)
    for invs in by_party.values():
        for n in (2, 3):
            for combo in combinations(invs, n):
                s = sum((i.total - i.amount_paid for i in combo), Decimal("0"))
                if abs(s - target) <= AMOUNT_TOLERANCE:
                    out.append(
                        _score(txn, list(combo), Decimal("0.35"), f"sum of {n} open invoices")
                    )
    out.sort(key=lambda c: (-c.score, len(c.invoices)))
    return out[:10]


def should_auto_accept(cands: list[Candidate]) -> Candidate | None:
    if not cands or cands[0].score < AUTO_ACCEPT_SCORE:
        return None
    if len(cands) > 1 and cands[0].score - cands[1].score < AUTO_ACCEPT_MARGIN:
        return None  # ambiguous: propose instead
    return cands[0]


def apply_match(
    txn: BankTransaction, invoices: list[Invoice], *, actor: Any, status: str
) -> Payment:
    """Create the Payment, allocate across invoices (oldest first), link the transaction."""
    if txn.match_status in (MatchStatus.AUTO, MatchStatus.MANUAL):
        raise ValueError("Transaction already matched.")
    direction = PaymentDirection.RECEIVED if txn.amount > 0 else PaymentDirection.MADE
    expected = "outward" if direction == PaymentDirection.RECEIVED else "inward"
    if any(i.direction != expected for i in invoices):
        kind = "credit" if txn.amount > 0 else "debit"
        raise ValueError(f"A {kind} cannot settle {invoices[0].direction} invoices.")
    with transaction.atomic():
        payment = Payment.objects.create(
            org=txn.bank_account.org,
            party=invoices[0].party,
            direction=direction,
            amount=abs(txn.amount),
            date=txn.date,
            method="neft",
            reference=txn.reference[:100] or txn.description[:100],
            created_by=actor if getattr(actor, "pk", None) else None,
        )
        remaining = abs(txn.amount)
        items: list[tuple[Invoice, Decimal]] = []
        for inv in sorted(invoices, key=lambda i: (i.due_date or i.invoice_date, i.invoice_date)):
            take = min(remaining, inv.total - inv.amount_paid)
            if take > 0:
                items.append((inv, take))
                remaining -= take
        allocate(payment, items, actor=actor)
        txn.matched_payment = payment
        txn.match_status = status
        txn.save(update_fields=["matched_payment", "match_status", "updated_at"])
        record(
            payment.org,
            actor=actor,
            entity=txn,
            action=f"bank.match.{status}",
            after={"payment": str(payment.pk), "invoices": [str(i.pk) for i in invoices]},
        )
    return payment


def auto_match(account_id: Any, *, actor: Any = None) -> dict[str, int]:
    matched = proposed = 0
    qs = BankTransaction.objects.filter(
        bank_account_id=account_id, match_status=MatchStatus.UNMATCHED
    ).select_related("bank_account__org")
    for txn in qs:
        cands = candidates_for(txn)
        pick = should_auto_accept(cands)
        if pick:
            apply_match(txn, pick.invoices, actor=actor, status=MatchStatus.AUTO)
            matched += 1
        elif cands:
            proposed += 1
    return {"matched": matched, "proposed": proposed}
