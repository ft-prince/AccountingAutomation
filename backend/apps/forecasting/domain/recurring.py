"""Recurring-expense pattern detection (PROJECT_SPECS §8.2).

Same party (first pass) or same category (second pass, on invoices not already
consumed), amount within ±15% of the cluster median, consecutive gaps inside one
periodicity band (28-31 / 88-92 / 360-370 days), at least 3 occurrences.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

PERIOD_BANDS: tuple[tuple[int, int], ...] = ((28, 31), (88, 92), (360, 370))
AMOUNT_TOLERANCE = Decimal("0.15")
MIN_OCCURRENCES = 3
CONFIDENCE_FULL_AT_OCCURRENCES = 6
CENT = Decimal("0.01")


@dataclass(frozen=True)
class ExpenseInvoice:
    key: str
    party_key: str | None
    category_key: str | None
    invoice_date: date
    amount: Decimal


@dataclass(frozen=True)
class Pattern:
    party_key: str | None
    category_key: str | None
    amount_p50: Decimal
    period_days: int
    next_expected: date
    confidence: Decimal
    occurrences: int
    invoice_keys: tuple[str, ...]


def median_decimal(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid].quantize(CENT, rounding=ROUND_HALF_UP)
    return ((ordered[mid - 1] + ordered[mid]) / 2).quantize(CENT, rounding=ROUND_HALF_UP)


def _median_int(values: Sequence[int]) -> int:
    return int(median_decimal([Decimal(v) for v in values]).to_integral_value(ROUND_HALF_UP))


def period_band(gap: int) -> int | None:
    for index, (low, high) in enumerate(PERIOD_BANDS):
        if low <= gap <= high:
            return index
    return None


def _longest_periodic_run(cluster: Sequence[ExpenseInvoice]) -> list[ExpenseInvoice]:
    """Members of the longest stretch of consecutive gaps sharing one band."""
    best: list[ExpenseInvoice] = []
    start = 0
    band: int | None = None
    for i in range(1, len(cluster)):
        gap_band = period_band((cluster[i].invoice_date - cluster[i - 1].invoice_date).days)
        if gap_band is None or gap_band != band:
            start = i - 1
            band = gap_band
        if band is not None and i - start + 1 > len(best):
            best = list(cluster[start : i + 1])
    return best if len(best) >= MIN_OCCURRENCES else []


def _pattern_from_run(run: Sequence[ExpenseInvoice]) -> Pattern:
    gaps = [(b.invoice_date - a.invoice_date).days for a, b in zip(run, run[1:], strict=False)]
    period = _median_int(gaps)
    confidence = min(Decimal(1), Decimal(len(run)) / CONFIDENCE_FULL_AT_OCCURRENCES)
    return Pattern(
        party_key=run[0].party_key,
        category_key=run[0].category_key,
        amount_p50=median_decimal([m.amount for m in run]),
        period_days=period,
        next_expected=run[-1].invoice_date + timedelta(days=period),
        confidence=confidence.quantize(CENT, rounding=ROUND_HALF_UP),
        occurrences=len(run),
        invoice_keys=tuple(m.key for m in run),
    )


def _near_median(members: Sequence[ExpenseInvoice]) -> list[ExpenseInvoice]:
    """Members within ±15% of the median amount. With an even count the median is the
    average of the middle pair; when the amounts are bimodal nothing is near it, so
    re-centre on the lower middle element (always non-empty, so callers make progress)."""
    amounts = sorted(m.amount for m in members)
    cluster = _within_tolerance(members, median_decimal(amounts))
    return cluster or _within_tolerance(members, amounts[len(amounts) // 2 - 1])


def _within_tolerance(members: Sequence[ExpenseInvoice], centre: Decimal) -> list[ExpenseInvoice]:
    return [m for m in members if abs(m.amount - centre) <= centre * AMOUNT_TOLERANCE]


def _patterns_in_group(members: Sequence[ExpenseInvoice]) -> list[Pattern]:
    remaining = sorted(members, key=lambda m: (m.invoice_date, m.key))
    found: list[Pattern] = []
    while len(remaining) >= MIN_OCCURRENCES:
        cluster = _near_median(remaining)
        run = _longest_periodic_run(cluster)
        drop = {m.key for m in (run or cluster)}
        if run:
            found.append(_pattern_from_run(run))
        remaining = [m for m in remaining if m.key not in drop]
    return found


def _grouped(
    invoices: Sequence[ExpenseInvoice], key_of: Callable[[ExpenseInvoice], str | None]
) -> dict[str, list[ExpenseInvoice]]:
    groups: dict[str, list[ExpenseInvoice]] = defaultdict(list)
    for inv in invoices:
        key = key_of(inv)
        if key is not None:
            groups[key].append(inv)
    return groups


def detect_patterns(invoices: Sequence[ExpenseInvoice]) -> tuple[Pattern, ...]:
    consumed: set[str] = set()
    patterns: list[Pattern] = []
    passes: tuple[Callable[[ExpenseInvoice], str | None], ...] = (
        lambda inv: inv.party_key,
        lambda inv: inv.category_key,
    )
    for key_of in passes:
        for _, members in sorted(_grouped(invoices, key_of).items()):
            fresh = [m for m in members if m.key not in consumed]
            for pattern in _patterns_in_group(fresh):
                patterns.append(pattern)
                consumed.update(pattern.invoice_keys)
    return tuple(patterns)
