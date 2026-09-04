"""Detect recurring expense patterns and persist them, keeping user decisions (§8.2)."""

from datetime import date
from uuid import UUID

from django.utils import timezone

from apps.accounts.models import Organization
from apps.forecasting.domain.recurring import Pattern, detect_patterns, period_band
from apps.forecasting.models import RecurringExpensePattern
from apps.forecasting.services.inputs import expense_invoices, invoice_states


def _uuid(key: str | None) -> UUID | None:
    return UUID(key) if key else None


def _matches(existing: RecurringExpensePattern, pattern: Pattern) -> bool:
    return (
        existing.party_id == _uuid(pattern.party_key)
        and existing.category_id == _uuid(pattern.category_key)
        and period_band(existing.period_days) == period_band(pattern.period_days)
    )


def detect_and_persist(org: Organization, as_of: date) -> list[RecurringExpensePattern]:
    patterns = detect_patterns(expense_invoices(invoice_states(org, as_of)))
    existing = list(RecurringExpensePattern.objects.for_org(org))
    now = timezone.now()
    out: list[RecurringExpensePattern] = []
    for pattern in patterns:
        row = next((e for e in existing if _matches(e, pattern)), None)
        if row is None:
            row = RecurringExpensePattern(
                org=org,
                party_id=_uuid(pattern.party_key),
                category_id=_uuid(pattern.category_key),
                user_confirmed=None,
            )
        row.amount_p50 = pattern.amount_p50
        row.period_days = pattern.period_days
        row.next_expected = pattern.next_expected
        row.confidence = pattern.confidence
        row.occurrences = pattern.occurrences
        row.last_detected_at = now
        row.save()
        out.append(row)
    return out
