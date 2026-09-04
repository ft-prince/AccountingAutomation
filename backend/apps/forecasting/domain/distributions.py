"""Per-party days_to_pay distributions (PROJECT_SPECS §8.2) and the long-tail
non-payment component (§8.3).

days_to_pay is measured relative to due_date: payment.date - due_date, negative when
early. Fallback chain: >= MIN_PARTY_SAMPLES paid invoices -> the party's own sample;
else the org-wide sample (same threshold); else a point mass at payment_terms_days
+ FALLBACK_GRACE_DAYS. Sampling is uniform over the stored samples.

Probabilities are floats: they only ever feed the Monte Carlo sampler, never money.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

MIN_PARTY_SAMPLES = 3
FALLBACK_GRACE_DAYS = 7
DEFAULT_TERMS_DAYS = 30
LONG_TAIL_DAYS = 120
NON_PAYMENT_FLOOR = 0.02

Source = Literal["party", "org", "terms"]


@dataclass(frozen=True)
class PaymentRecord:
    """One invoice's payment behaviour. For open invoices days_to_pay is the lateness
    so far (as_of - due_date) and only feeds the non-payment share."""

    party_key: str
    days_to_pay: int
    is_paid: bool = True


@dataclass(frozen=True)
class Distribution:
    samples: tuple[int, ...]
    non_payment_probability: float
    source: Source


def _paid_days(records: Iterable[PaymentRecord]) -> tuple[int, ...]:
    return tuple(r.days_to_pay for r in records if r.is_paid)


def non_payment_share(records: Sequence[PaymentRecord]) -> float:
    """Share of invoices (paid or open) more than LONG_TAIL_DAYS late, floored (§8.3)."""
    if not records:
        return NON_PAYMENT_FLOOR
    late = sum(1 for r in records if r.days_to_pay > LONG_TAIL_DAYS)
    return max(NON_PAYMENT_FLOOR, late / len(records))


def build_distribution(
    party_key: str, records: Sequence[PaymentRecord], terms_days: int
) -> Distribution:
    own = [r for r in records if r.party_key == party_key]
    own_days = _paid_days(own)
    if len(own_days) >= MIN_PARTY_SAMPLES:
        return Distribution(own_days, non_payment_share(own), "party")
    org_days = _paid_days(records)
    if len(org_days) >= MIN_PARTY_SAMPLES:
        return Distribution(org_days, non_payment_share(records), "org")
    return Distribution((terms_days + FALLBACK_GRACE_DAYS,), NON_PAYMENT_FLOOR, "terms")


def build_distributions(
    records: Sequence[PaymentRecord], terms_by_party: Mapping[str, int]
) -> dict[str, Distribution]:
    keys = set(terms_by_party) | {r.party_key for r in records}
    return {
        key: build_distribution(key, records, terms_by_party.get(key, DEFAULT_TERMS_DAYS))
        for key in sorted(keys)
    }


def shift_distribution(dist: Distribution, days: int) -> Distribution:
    """Return a copy with every sample moved by `days` (collection-policy scenarios, §8.4)."""
    return Distribution(
        samples=tuple(d + days for d in dist.samples),
        non_payment_probability=dist.non_payment_probability,
        source=dist.source,
    )
