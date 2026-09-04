"""Expense anomalies, duplicate detection and revenue concentration (PROJECT_SPECS §8.5).

Robust z = 0.6745 * (x - median) / MAD per (party, category) on amount and on the
inter-arrival gap; flagged when |z| > 3. When MAD is 0 (identical history) the scale
falls back to 1% of |median| (min 1 unit) so a genuine jump is still caught.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import numpy as np

Z_THRESHOLD = Decimal("3")
MAD_TO_SIGMA = 0.6745
MAD_FLOOR_SHARE = 0.01
MIN_GROUP_SIZE = 4
NEW_VENDOR_MAX_INVOICES = 3
NEW_VENDOR_AMOUNT = Decimal("50000")
DUPLICATE_AMOUNT_TOLERANCE = Decimal("1")
DUPLICATE_WINDOW_DAYS = 7
TOP1_FLAG_SHARE = Decimal("0.40")
TOP3_FLAG_SHARE = Decimal("0.70")
TOP_N = 3
TWO_DP = Decimal("0.01")
FOUR_DP = Decimal("0.0001")
PAISE_PER_RUPEE = 100

Kind = Literal["amount", "gap", "new_vendor", "duplicate"]


@dataclass(frozen=True)
class ExpenseRecord:
    key: str
    party_key: str
    category_key: str | None
    invoice_date: date
    amount: Decimal


@dataclass(frozen=True)
class Anomaly:
    key: str
    kind: Kind
    party_key: str
    category_key: str | None
    z: Decimal | None
    detail: str
    related_key: str | None = None


@dataclass(frozen=True)
class RevenueRecord:
    party_key: str
    amount: Decimal


@dataclass(frozen=True)
class Concentration:
    top1_party: str | None
    top1_share: Decimal
    top3_parties: tuple[str, ...]
    top3_share: Decimal
    is_top1_flagged: bool
    is_top3_flagged: bool


def robust_z(values: Sequence[int]) -> list[Decimal]:
    arr = np.asarray(values, dtype=np.float64)
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    scale = mad if mad > 0 else max(abs(median) * MAD_FLOOR_SHARE, 1.0)
    z = MAD_TO_SIGMA * (arr - median) / scale
    return [Decimal(f"{v:.6f}").quantize(TWO_DP, rounding=ROUND_HALF_UP) for v in z]


def _paise(amount: Decimal) -> int:
    return int(amount.quantize(TWO_DP, rounding=ROUND_HALF_UP) * PAISE_PER_RUPEE)


def _in_window(record: ExpenseRecord, window_start: date | None) -> bool:
    return window_start is None or record.invoice_date >= window_start


def _amount_flags(group: Sequence[ExpenseRecord], window_start: date | None) -> list[Anomaly]:
    zs = robust_z([_paise(r.amount) for r in group])
    return [
        Anomaly(r.key, "amount", r.party_key, r.category_key, z, f"amount z={z}")
        for r, z in zip(group, zs, strict=True)
        if abs(z) > Z_THRESHOLD and _in_window(r, window_start)
    ]


def _gap_flags(group: Sequence[ExpenseRecord], window_start: date | None) -> list[Anomaly]:
    gaps = [(b.invoice_date - a.invoice_date).days for a, b in zip(group, group[1:], strict=False)]
    zs = robust_z(gaps)
    return [
        Anomaly(r.key, "gap", r.party_key, r.category_key, z, f"gap {gap}d z={z}")
        for r, gap, z in zip(group[1:], gaps, zs, strict=True)
        if abs(z) > Z_THRESHOLD and _in_window(r, window_start)
    ]


def _new_vendor_flags(records: Sequence[ExpenseRecord], window_start: date | None) -> list[Anomaly]:
    per_party: dict[str, int] = defaultdict(int)
    for r in records:
        per_party[r.party_key] += 1
    return [
        Anomaly(r.key, "new_vendor", r.party_key, r.category_key, None, f"new vendor, {r.amount}")
        for r in records
        if per_party[r.party_key] <= NEW_VENDOR_MAX_INVOICES
        and r.amount > NEW_VENDOR_AMOUNT
        and _in_window(r, window_start)
    ]


def detect_expense_anomalies(
    records: Sequence[ExpenseRecord], window_start: date | None = None
) -> tuple[Anomaly, ...]:
    """Flags only records dated on/after window_start; statistics use everything."""
    groups: dict[tuple[str, str | None], list[ExpenseRecord]] = defaultdict(list)
    for r in sorted(records, key=lambda r: (r.invoice_date, r.key)):
        groups[(r.party_key, r.category_key)].append(r)
    flags: list[Anomaly] = []
    for _, group in sorted(groups.items()):
        if len(group) >= MIN_GROUP_SIZE:
            flags += _amount_flags(group, window_start) + _gap_flags(group, window_start)
    return tuple(flags + _new_vendor_flags(records, window_start))


def detect_duplicates(records: Sequence[ExpenseRecord]) -> tuple[Anomaly, ...]:
    """Same party, amount within ±1, dated within 7 days: the later one is flagged."""
    by_party: dict[str, list[ExpenseRecord]] = defaultdict(list)
    for r in sorted(records, key=lambda r: (r.invoice_date, r.key)):
        by_party[r.party_key].append(r)
    out: list[Anomaly] = []
    for _, group in sorted(by_party.items()):
        for j, later in enumerate(group):
            for earlier in group[:j]:
                close_in_time = (
                    later.invoice_date - earlier.invoice_date
                ).days <= DUPLICATE_WINDOW_DAYS
                close_in_amount = abs(later.amount - earlier.amount) <= DUPLICATE_AMOUNT_TOLERANCE
                if close_in_time and close_in_amount:
                    detail = f"possible duplicate of {earlier.key}"
                    out.append(
                        Anomaly(
                            later.key,
                            "duplicate",
                            later.party_key,
                            later.category_key,
                            None,
                            detail,
                            related_key=earlier.key,
                        )
                    )
    return tuple(out)


def revenue_concentration(records: Sequence[RevenueRecord]) -> Concentration:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for r in records:
        totals[r.party_key] += r.amount
    total = sum(totals.values(), Decimal(0))
    if total <= 0:
        return Concentration(None, Decimal(0), (), Decimal(0), False, False)
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top1_share = (ranked[0][1] / total).quantize(FOUR_DP, rounding=ROUND_HALF_UP)
    top3 = ranked[:TOP_N]
    top3_share = (sum((v for _, v in top3), Decimal(0)) / total).quantize(
        FOUR_DP, rounding=ROUND_HALF_UP
    )
    return Concentration(
        top1_party=ranked[0][0],
        top1_share=top1_share,
        top3_parties=tuple(k for k, _ in top3),
        top3_share=top3_share,
        is_top1_flagged=top1_share > TOP1_FLAG_SHARE,
        is_top3_flagged=top3_share > TOP3_FLAG_SHARE,
    )
