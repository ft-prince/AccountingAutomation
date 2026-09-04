"""Customer payment-delay risk (PROJECT_SPECS §8.5).

Logistic-style score over: mean and standard deviation of days_to_pay (relative to
due_date), the trend over the last TREND_WINDOW invoices, the share of the open balance
that is overdue, and open balance vs credit_limit. Bands: low / watch / high, with the
drivers that pushed the score listed in plain words.

Statistics are floats (not money); the boundary types are Decimal.
"""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

DAYS_SCALE = 30.0
TREND_WINDOW = 6
MIN_SAMPLES_FOR_TREND = 4

WEIGHT_MEAN = 1.5
WEIGHT_STD = 0.5
WEIGHT_TREND = 1.0
WEIGHT_OVERDUE = 2.0
WEIGHT_UTILISATION = 1.5
BIAS = -2.0

LOW_MAX = Decimal("0.35")
WATCH_MAX = Decimal("0.65")

DRIVER_MEAN_DAYS = 15.0
DRIVER_STD_DAYS = 15.0
DRIVER_TREND_DAYS = 7.0
DRIVER_OVERDUE_SHARE = 0.25
DRIVER_UTILISATION = 0.8

ONE_DP = Decimal("0.1")
TWO_DP = Decimal("0.01")
THREE_DP = Decimal("0.001")

Band = Literal["low", "watch", "high"]


@dataclass(frozen=True)
class CustomerHistory:
    party_key: str
    days_to_pay: tuple[int, ...]  # chronological, paid invoices only
    open_balance: Decimal
    overdue_balance: Decimal
    credit_limit: Decimal | None


@dataclass(frozen=True)
class RiskScore:
    party_key: str
    score: Decimal
    band: Band
    drivers: tuple[str, ...]
    mean_days: Decimal
    std_days: Decimal
    trend_days: Decimal
    share_overdue: Decimal
    utilisation: Decimal | None


def _dec(value: float, places: Decimal) -> Decimal:
    return Decimal(f"{value:.6f}").quantize(places, rounding=ROUND_HALF_UP)


def _trend(days: Sequence[int]) -> float:
    recent = days[-TREND_WINDOW:]
    if len(recent) < MIN_SAMPLES_FOR_TREND:
        return 0.0
    half = len(recent) // 2
    return statistics.fmean(recent[half:]) - statistics.fmean(recent[:half])


def _ratio(numerator: Decimal, denominator: Decimal) -> float:
    return statistics.fmean([numerator / denominator]) if denominator > 0 else 0.0


def _band(score: Decimal) -> Band:
    if score < LOW_MAX:
        return "low"
    if score < WATCH_MAX:
        return "watch"
    return "high"


def _drivers(
    has_history: bool, mean: float, std: float, trend: float, overdue: float, util: float | None
) -> tuple[str, ...]:
    out: list[str] = []
    if not has_history:
        out.append("no payment history")
    if mean > DRIVER_MEAN_DAYS:
        out.append(f"avg {mean:.1f} days late")
    if std > DRIVER_STD_DAYS:
        out.append(f"erratic timing (sd {std:.1f} days)")
    if trend > DRIVER_TREND_DAYS:
        out.append(f"slowing: +{trend:.1f} days over last {TREND_WINDOW}")
    if overdue > DRIVER_OVERDUE_SHARE:
        out.append(f"{overdue * 100:.0f}% of open balance overdue")
    if util is not None and util > DRIVER_UTILISATION:
        out.append(f"{util * 100:.0f}% of credit limit used")
    return tuple(out)


def score_customer(history: CustomerHistory) -> RiskScore:
    days = history.days_to_pay
    mean = statistics.fmean(days) if days else 0.0
    std = statistics.pstdev(days) if days else 0.0
    trend = _trend(days)
    overdue = _ratio(history.overdue_balance, history.open_balance)
    limit = history.credit_limit
    util = _ratio(history.open_balance, limit) if limit is not None and limit > 0 else None
    z = (
        WEIGHT_MEAN * mean / DAYS_SCALE
        + WEIGHT_STD * std / DAYS_SCALE
        + WEIGHT_TREND * trend / DAYS_SCALE
        + WEIGHT_OVERDUE * overdue
        + WEIGHT_UTILISATION * (util or 0.0)
        + BIAS
    )
    score = _dec(1.0 / (1.0 + math.exp(-z)), THREE_DP)
    return RiskScore(
        party_key=history.party_key,
        score=score,
        band=_band(score),
        drivers=_drivers(bool(days), mean, std, trend, overdue, util),
        mean_days=_dec(mean, ONE_DP),
        std_days=_dec(std, ONE_DP),
        trend_days=_dec(trend, ONE_DP),
        share_overdue=_dec(overdue, TWO_DP),
        utilisation=_dec(util, TWO_DP) if util is not None else None,
    )


def score_customers(histories: Sequence[CustomerHistory]) -> tuple[RiskScore, ...]:
    scored = [score_customer(h) for h in histories]
    return tuple(sorted(scored, key=lambda s: (-s.score, s.party_key)))
