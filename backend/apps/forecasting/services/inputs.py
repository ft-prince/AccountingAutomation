"""Assemble engine inputs from the books as of a date (PROJECT_SPECS §8.2).

"As of" semantics everywhere so the same code serves live runs and rolling-origin
backtests: only invoices dated on/before as_of count, and only allocations whose
payment date is on/before as_of reduce what is outstanding.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, F, Max, Min, Sum

from apps.accounts.models import Organization
from apps.forecasting.domain.distributions import PaymentRecord, build_distributions
from apps.forecasting.domain.engine import (
    APItem,
    ARItem,
    Expected,
    FixedLine,
    ForecastInputs,
    OpeningCash,
    Recurring,
    Statutory,
)
from apps.forecasting.domain.recurring import (
    ExpenseInvoice,
    Pattern,
    detect_patterns,
    period_band,
)
from apps.forecasting.models import ExpectedInvoice, FixedCashflowLine, RecurringExpensePattern
from apps.gst.domain.periods import StateGroup, due_date_gstr3b
from apps.invoices.models import Direction, Invoice, InvoiceStatus, PaymentStatus
from apps.parties.models import Party
from apps.payments.models import (
    BankAccount,
    BankBalanceSnapshot,
    BankTransaction,
    PaymentAllocation,
)

ZERO = Decimal("0")
MIN_HISTORY_DAYS = 90
UNCONFIRMED_WEIGHT = Decimal("0.7")
CONFIRMED_WEIGHT = Decimal("1")
QRMP = False  # v1: monthly filers, state group 1 (PROJECT_SPECS §3.8 defaults)
STATE_GROUP: StateGroup = 1


@dataclass(frozen=True)
class InvoiceState:
    """A confirmed invoice as of a date: what is still outstanding and, if settled, when."""

    invoice: Invoice
    outstanding: Decimal
    due: date
    paid_on: date | None

    @property
    def party_key(self) -> str:
        return str(self.invoice.party_id)


def invoice_states(org: Organization, as_of: date) -> list[InvoiceState]:
    invoices = (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED, invoice_date__lte=as_of)
        .exclude(payment_status=PaymentStatus.WRITTEN_OFF)
        .select_related("party")
        .prefetch_related("lines")
        .order_by("invoice_date", "created_at")
    )
    paid = {
        row["invoice_id"]: (row["paid"], row["last"])
        for row in PaymentAllocation.objects.filter(invoice__org=org, payment__date__lte=as_of)
        .values("invoice_id")
        .annotate(paid=Sum("amount"), last=Max("payment__date"))
    }
    states: list[InvoiceState] = []
    for inv in invoices:
        amount, last = paid.get(inv.pk, (ZERO, None))
        outstanding = inv.total - amount
        due = inv.due_date or inv.invoice_date + timedelta(days=inv.party.payment_terms_days)
        states.append(InvoiceState(inv, outstanding, due, last if outstanding <= 0 else None))
    return states


def outward(states: list[InvoiceState]) -> list[InvoiceState]:
    return [s for s in states if s.invoice.direction == Direction.OUTWARD]


def inward(states: list[InvoiceState]) -> list[InvoiceState]:
    return [s for s in states if s.invoice.direction == Direction.INWARD]


def payment_records(states: list[InvoiceState], as_of: date) -> list[PaymentRecord]:
    records: list[PaymentRecord] = []
    for s in outward(states):
        if s.paid_on is not None:
            records.append(PaymentRecord(s.party_key, (s.paid_on - s.due).days, True))
        else:
            records.append(PaymentRecord(s.party_key, (as_of - s.due).days, False))
    return records


def terms_by_party(org: Organization) -> dict[str, int]:
    return {
        str(pk): terms
        for pk, terms in Party.objects.for_org(org).values_list("pk", "payment_terms_days")
    }


def ar_items(states: list[InvoiceState]) -> tuple[ARItem, ...]:
    return tuple(
        ARItem(s.party_key, s.outstanding, s.due) for s in outward(states) if s.outstanding > 0
    )


def ap_items(states: list[InvoiceState]) -> tuple[APItem, ...]:
    return tuple(
        APItem(s.outstanding, s.due, s.party_key) for s in inward(states) if s.outstanding > 0
    )


def expense_invoices(states: list[InvoiceState]) -> list[ExpenseInvoice]:
    out: list[ExpenseInvoice] = []
    for s in inward(states):
        first_line = next(iter(s.invoice.lines.all()), None)
        category = first_line.category_id if first_line is not None else None
        out.append(
            ExpenseInvoice(
                key=str(s.invoice.pk),
                party_key=s.party_key,
                category_key=str(category) if category else None,
                invoice_date=s.invoice.invoice_date,
                amount=s.invoice.total,
            )
        )
    return out


def _latest_balance(snapshot: BankBalanceSnapshot | None, txn: BankTransaction | None) -> Decimal:
    if snapshot is None and txn is None:
        return ZERO
    if txn is None or (snapshot is not None and snapshot.date >= txn.date):
        assert snapshot is not None
        return snapshot.balance
    assert txn.balance_after is not None
    return txn.balance_after


def opening_cash(org: Organization, as_of: date) -> Decimal:
    """Per active bank account, the newest of (manual snapshot, statement balance_after);
    org-level snapshots (no account) are added on top."""
    total = ZERO
    snapshots = BankBalanceSnapshot.objects.for_org(org).filter(date__lte=as_of)
    for account in BankAccount.objects.for_org(org).filter(is_active=True):
        snap = snapshots.filter(bank_account=account).order_by("-date", "-created_at").first()
        txn = (
            BankTransaction.objects.filter(
                bank_account=account, date__lte=as_of, balance_after__isnull=False
            )
            .order_by("-date", "-created_at")
            .first()
        )
        total += _latest_balance(snap, txn)
    org_level = snapshots.filter(bank_account__isnull=True).order_by("-date", "-created_at").first()
    if org_level is not None:
        total += org_level.balance
    return total


def statutory_outflows(org: Organization, as_of: date) -> tuple[Statutory, ...]:
    """GSTR-3B net payable per period not yet due: output tax on confirmed outward minus
    eligible ITC on confirmed inward, on due_date_gstr3b (§8.2, §3.8)."""
    tax = F("cgst") + F("sgst") + F("igst") + F("cess")
    rows = (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED, invoice_date__lte=as_of)
        .values("period_month", "direction", "itc_eligible")
        .annotate(tax=Sum(tax, output_field=DecimalField(max_digits=14, decimal_places=2)))
    )
    net: dict[str, Decimal] = {}
    for row in rows:
        month = row["period_month"]
        if row["direction"] == Direction.OUTWARD:
            net[month] = net.get(month, ZERO) + row["tax"]
        elif row["itc_eligible"]:
            net[month] = net.get(month, ZERO) - row["tax"]
    out: list[Statutory] = []
    for month, amount in sorted(net.items()):
        due = due_date_gstr3b(f"{month[5:7]}{month[:4]}", QRMP, STATE_GROUP)
        if due > as_of and amount > 0:
            out.append(Statutory(amount, due))
    return tuple(out)


def fixed_lines(org: Organization) -> tuple[FixedLine, ...]:
    return tuple(
        FixedLine(f.name, f.amount, f.next_date, f.cadence, f.direction)  # type: ignore[arg-type]
        for f in FixedCashflowLine.objects.for_org(org).filter(is_active=True).order_by("name")
    )


def expected_invoices(org: Organization, as_of: date) -> tuple[Expected, ...]:
    return tuple(
        Expected(e.amount, e.expected_date, e.probability, str(e.party_id))
        for e in ExpectedInvoice.objects.for_org(org)
        .filter(expected_date__gte=as_of)
        .order_by("expected_date")
    )


def stored_recurring(org: Organization) -> tuple[Recurring, ...]:
    """Persisted patterns; dismissed ones are excluded, unconfirmed weighted 0.7 (§8.2)."""
    return tuple(
        Recurring(
            p.amount_p50,
            p.next_expected,
            p.period_days,
            CONFIRMED_WEIGHT if p.user_confirmed else UNCONFIRMED_WEIGHT,
        )
        for p in RecurringExpensePattern.objects.for_org(org)
        .exclude(user_confirmed=False)
        .order_by("next_expected")
    )


def _decision_for(pattern: Pattern, stored: list[RecurringExpensePattern]) -> bool | None:
    """The user's current confirm/dismiss decision for an equivalent stored pattern."""
    for row in stored:
        same_party = (
            str(row.party_id) == pattern.party_key if row.party_id else not pattern.party_key
        )
        same_cat = (
            str(row.category_id) == pattern.category_key
            if row.category_id
            else not pattern.category_key
        )
        if (
            same_party
            and same_cat
            and period_band(row.period_days) == period_band(pattern.period_days)
        ):
            return row.user_confirmed
    return None


def backtest_recurring(org: Organization, states: list[InvoiceState]) -> tuple[Recurring, ...]:
    """Patterns detectable at the origin, weighted by the user's decision today so the
    backtest scores the configuration the live forecast actually runs with."""
    stored = list(RecurringExpensePattern.objects.for_org(org))
    out: list[Recurring] = []
    for pattern in detect_patterns(expense_invoices(states)):
        decision = _decision_for(pattern, stored)
        if decision is False:
            continue
        weight = CONFIRMED_WEIGHT if decision else UNCONFIRMED_WEIGHT
        out.append(
            Recurring(pattern.amount_p50, pattern.next_expected, pattern.period_days, weight)
        )
    return tuple(out)


def recurring_vendor_keys(states: list[InvoiceState]) -> set[str]:
    """Parties whose bills form a recurring pattern in `states` (the outflows the engine
    forecasts beyond the invoices it already knows)."""
    return {p.party_key for p in detect_patterns(expense_invoices(states)) if p.party_key}


def history_days(org: Organization, as_of: date) -> int:
    earliest = (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED)
        .aggregate(d=Min("invoice_date"))["d"]
    )
    return max(0, (as_of - earliest).days) if earliest else 0


def assemble_inputs(
    org: Organization, as_of: date, *, for_backtest: bool = False
) -> ForecastInputs:
    """Live runs use everything. Backtest origins use only what actual allocated payments
    can be compared against: AR, AP and recurring patterns detectable at the time, from a
    zero opening balance."""
    states = invoice_states(org, as_of)
    distributions = build_distributions(payment_records(states, as_of), terms_by_party(org))
    if for_backtest:
        return ForecastInputs(
            opening=OpeningCash(ZERO, as_of),
            ar=ar_items(states),
            ap=ap_items(states),
            recurring=backtest_recurring(org, states),
            distributions=distributions,
        )
    return ForecastInputs(
        opening=OpeningCash(opening_cash(org, as_of), as_of),
        ar=ar_items(states),
        ap=ap_items(states),
        recurring=stored_recurring(org),
        fixed_lines=fixed_lines(org),
        statutory=statutory_outflows(org, as_of),
        expected=expected_invoices(org, as_of),
        distributions=distributions,
    )


def inputs_hash(inputs: ForecastInputs) -> str:
    payload: dict[str, Any] = asdict(inputs)
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
