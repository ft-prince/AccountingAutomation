"""Customer risk, expense anomalies and revenue concentration (PROJECT_SPECS §8.5)."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.accounts.models import Organization
from apps.forecasting.domain.anomalies import (
    Anomaly,
    ExpenseRecord,
    RevenueRecord,
    detect_duplicates,
    detect_expense_anomalies,
    revenue_concentration,
)
from apps.forecasting.domain.risk import CustomerHistory, score_customers
from apps.forecasting.services.inputs import InvoiceState, invoice_states, inward, outward
from apps.parties.models import ExpenseCategory, Party

ZERO = Decimal("0")
ANOMALY_WINDOW_DAYS = 90
CONCENTRATION_WINDOW_DAYS = 365


def _party_names(org: Organization) -> dict[str, str]:
    return {str(p.pk): str(p) for p in Party.objects.for_org(org)}


def _histories(states: list[InvoiceState], as_of: date) -> list[CustomerHistory]:
    paid: dict[str, list[tuple[date, int]]] = defaultdict(list)
    open_balance: dict[str, Decimal] = defaultdict(Decimal)
    overdue: dict[str, Decimal] = defaultdict(Decimal)
    limits: dict[str, Decimal | None] = {}
    for s in outward(states):
        limits[s.party_key] = s.invoice.party.credit_limit
        if s.paid_on is not None:
            paid[s.party_key].append((s.paid_on, (s.paid_on - s.due).days))
        else:
            open_balance[s.party_key] += s.outstanding
            if s.due < as_of:
                overdue[s.party_key] += s.outstanding
    return [
        CustomerHistory(
            party_key=key,
            days_to_pay=tuple(d for _, d in sorted(paid[key])),
            open_balance=open_balance[key],
            overdue_balance=overdue[key],
            credit_limit=limits[key],
        )
        for key in sorted(limits)
    ]


def customer_risk(org: Organization, as_of: date) -> list[dict[str, Any]]:
    names = _party_names(org)
    scores = score_customers(_histories(invoice_states(org, as_of), as_of))
    return [
        {
            "party": s.party_key,
            "party_name": names.get(s.party_key, ""),
            "score": str(s.score),
            "band": s.band,
            "drivers": list(s.drivers),
            "mean_days": str(s.mean_days),
            "std_days": str(s.std_days),
            "trend_days": str(s.trend_days),
            "share_overdue": str(s.share_overdue),
            "utilisation": str(s.utilisation) if s.utilisation is not None else None,
        }
        for s in scores
    ]


def _expense_records(states: list[InvoiceState]) -> list[ExpenseRecord]:
    out: list[ExpenseRecord] = []
    for s in inward(states):
        first_line = next(iter(s.invoice.lines.all()), None)
        category = first_line.category_id if first_line is not None else None
        out.append(
            ExpenseRecord(
                key=str(s.invoice.pk),
                party_key=s.party_key,
                category_key=str(category) if category else None,
                invoice_date=s.invoice.invoice_date,
                amount=s.invoice.total,
            )
        )
    return out


def _anomaly_dict(a: Anomaly, names: dict[str, str], categories: dict[str, str]) -> dict[str, Any]:
    return {
        "invoice": a.key,
        "kind": a.kind,
        "party": a.party_key,
        "party_name": names.get(a.party_key, ""),
        "category": a.category_key,
        "category_name": categories.get(a.category_key or "", ""),
        "z": str(a.z) if a.z is not None else None,
        "detail": a.detail,
        "related_invoice": a.related_key,
    }


def anomalies(org: Organization, as_of: date) -> dict[str, Any]:
    states = invoice_states(org, as_of)
    names = _party_names(org)
    categories = {str(c.pk): c.name for c in ExpenseCategory.objects.all()}
    records = _expense_records(states)
    window_start = as_of - timedelta(days=ANOMALY_WINDOW_DAYS)
    flags = detect_expense_anomalies(records, window_start=window_start)
    duplicates = tuple(
        d
        for d in detect_duplicates(records)
        if any(r.key == d.key and r.invoice_date >= window_start for r in records)
    )
    revenue = [
        RevenueRecord(s.party_key, s.invoice.total)
        for s in outward(states)
        if s.invoice.invoice_date > as_of - timedelta(days=CONCENTRATION_WINDOW_DAYS)
    ]
    conc = revenue_concentration(revenue)
    return {
        "as_of": as_of.isoformat(),
        "window_days": ANOMALY_WINDOW_DAYS,
        "expenses": [_anomaly_dict(a, names, categories) for a in flags],
        "duplicates": [_anomaly_dict(a, names, categories) for a in duplicates],
        "concentration": {
            "top1_party": conc.top1_party,
            "top1_party_name": names.get(conc.top1_party or "", ""),
            "top1_share": str(conc.top1_share),
            "top3_parties": list(conc.top3_parties),
            "top3_share": str(conc.top3_share),
            "is_top1_flagged": conc.is_top1_flagged,
            "is_top3_flagged": conc.is_top3_flagged,
        },
    }
