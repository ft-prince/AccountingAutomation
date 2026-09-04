"""§6.7 metrics: time-to-first-draft, review time, edit distance, approval rate by intent,
flags per 100 drafts, replies per day (last 7). Rates are Decimal strings, never floats."""

from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, Min
from django.utils import timezone

from apps.mail.models import DraftStatus, EmailDraft, EmailMessage, EmailThread, MessageDirection

DAYS = 7
HUNDRED = Decimal("100")
RATE_PLACES = Decimal("0.0001")
REVIEWED = (
    DraftStatus.APPROVED,
    DraftStatus.EDITED_APPROVED,
    DraftStatus.SENT,
    DraftStatus.REJECTED,
)
APPROVED = (DraftStatus.APPROVED, DraftStatus.EDITED_APPROVED, DraftStatus.SENT)


def _avg_seconds(values: list[float]) -> int | None:
    return int(round(sum(values) / len(values))) if values else None


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0000"
    return str((Decimal(numerator) / Decimal(denominator)).quantize(RATE_PLACES, ROUND_HALF_UP))


def time_to_first_draft(org: Any) -> int | None:
    rows = (
        EmailThread.objects.for_org(org)
        .filter(drafts__isnull=False, last_inbound_at__isnull=False)
        .annotate(first_draft_at=Min("drafts__created_at"))
        .values_list("last_inbound_at", "first_draft_at")
    )
    return _avg_seconds([(first - inbound).total_seconds() for inbound, first in rows])


def review_time(org: Any) -> int | None:
    rows = (
        EmailDraft.objects.for_org(org)
        .filter(reviewed_at__isnull=False)
        .values_list("created_at", "reviewed_at")
    )
    return _avg_seconds([(reviewed - created).total_seconds() for created, reviewed in rows])


def mean_edit_distance(org: Any) -> str | None:
    values = list(
        EmailDraft.objects.for_org(org)
        .filter(edit_distance__isnull=False)
        .values_list("edit_distance", flat=True)
    )
    if not values:
        return None
    return str(
        (Decimal(sum(values)) / Decimal(len(values))).quantize(Decimal("0.01"), ROUND_HALF_UP)
    )


def approval_rate_by_intent(org: Any) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"approved": 0, "reviewed": 0})
    rows = (
        EmailDraft.objects.for_org(org)
        .filter(status__in=REVIEWED)
        .values("thread__intent", "status")
        .annotate(n=Count("id"))
    )
    for row in rows:
        intent = row["thread__intent"] or "unclassified"
        counts[intent]["reviewed"] += row["n"]
        if row["status"] in APPROVED:
            counts[intent]["approved"] += row["n"]
    return {
        intent: {**c, "rate": _ratio(c["approved"], c["reviewed"])}
        for intent, c in sorted(counts.items())
    }


def flags_per_100_drafts(org: Any) -> str:
    drafts = list(EmailDraft.objects.for_org(org).values_list("guardrail_flags", flat=True))
    if not drafts:
        return "0.00"
    total = sum(len(f) for f in drafts)
    return str(
        (Decimal(total) * HUNDRED / Decimal(len(drafts))).quantize(Decimal("0.01"), ROUND_HALF_UP)
    )


def replies_per_day(org: Any) -> list[dict[str, Any]]:
    today = timezone.localdate()
    start = today - timedelta(days=DAYS - 1)
    sent = EmailMessage.objects.for_org(org).filter(
        direction=MessageDirection.OUTBOUND, thread__isnull=False, date__date__gte=start
    )
    per_day: dict[str, int] = defaultdict(int)
    for d in sent.values_list("date", flat=True):
        per_day[timezone.localtime(d).date().isoformat()] += 1
    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "count": per_day[(start + timedelta(days=i)).isoformat()],
        }
        for i in range(DAYS)
    ]


def compute(org: Any) -> dict[str, Any]:
    return {
        "time_to_first_draft_seconds": time_to_first_draft(org),
        "review_time_seconds": review_time(org),
        "mean_edit_distance": mean_edit_distance(org),
        "approval_rate_by_intent": approval_rate_by_intent(org),
        "flags_per_100_drafts": flags_per_100_drafts(org),
        "replies_per_day": replies_per_day(org),
    }
