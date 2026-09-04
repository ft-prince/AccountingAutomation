"""Cashflow engine (PROJECT_SPECS §8.3): deterministic path + seeded Monte Carlo bands.

Day k of the horizon is as_of + k for k in 1..horizon_days. Anything dated on or before
as_of that is still open lands on day 1; anything beyond the horizon is ignored.

Money: Decimal at the boundary, int64 paise inside numpy. The deterministic path is
plain Decimal arithmetic. float64 appears only in the sampler's uniform draws.
"""

import calendar
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import numpy as np
import numpy.typing as npt

from apps.forecasting.domain.distributions import Distribution

DEFAULT_N_PATHS = 2000
DEFAULT_HORIZON_DAYS = 91
RECURRING_JITTER_DAYS = 3
BAND_QUANTILES = (0.1, 0.5, 0.9)
PAISE = Decimal("0.01")
PAISE_PER_RUPEE = 100
MONTHS_PER_YEAR = 12

Cadence = Literal["monthly", "quarterly", "yearly", "once"]
Direction = Literal["inflow", "outflow"]
CADENCE_MONTHS: dict[str, int] = {"monthly": 1, "quarterly": 3, "yearly": 12}

IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class OpeningCash:
    amount: Decimal
    as_of: date


@dataclass(frozen=True)
class ARItem:
    party_key: str
    amount: Decimal
    due_date: date


@dataclass(frozen=True)
class APItem:
    amount: Decimal
    due_date: date
    party_key: str | None = None


@dataclass(frozen=True)
class Recurring:
    amount: Decimal
    next_expected: date
    period_days: int
    weight: Decimal = Decimal("1")


@dataclass(frozen=True)
class FixedLine:
    name: str
    amount: Decimal
    next_date: date
    cadence: Cadence
    direction: Direction


@dataclass(frozen=True)
class Statutory:
    amount: Decimal
    date: date


@dataclass(frozen=True)
class Expected:
    amount: Decimal
    expected_date: date
    probability: Decimal
    party_key: str | None = None


@dataclass(frozen=True)
class ForecastInputs:
    opening: OpeningCash
    ar: tuple[ARItem, ...] = ()
    ap: tuple[APItem, ...] = ()
    recurring: tuple[Recurring, ...] = ()
    fixed_lines: tuple[FixedLine, ...] = ()
    statutory: tuple[Statutory, ...] = ()
    expected: tuple[Expected, ...] = ()
    distributions: Mapping[str, Distribution] = field(default_factory=dict)


@dataclass(frozen=True)
class DayPoint:
    date: date
    deterministic: Decimal
    p10: Decimal | None
    p50: Decimal | None
    p90: Decimal | None


@dataclass(frozen=True)
class ForecastResult:
    as_of: date
    horizon_days: int
    n_paths: int
    seed: int
    points: tuple[DayPoint, ...]
    runway_date: date | None


@dataclass(frozen=True)
class _Event:
    """A cash movement on a horizon day index (1-based). Signed paise."""

    day: int
    paise: int


def to_paise(amount: Decimal) -> int:
    return int(amount.quantize(PAISE, rounding=ROUND_HALF_UP) * PAISE_PER_RUPEE)


def from_paise(paise: int) -> Decimal:
    return (Decimal(paise) / PAISE_PER_RUPEE).quantize(PAISE)


def add_months(d: date, months: int) -> date:
    index = d.year * MONTHS_PER_YEAR + (d.month - 1) + months
    year, month = divmod(index, MONTHS_PER_YEAR)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _day_index(d: date, as_of: date) -> int:
    """1-based horizon day; past/today collapse to day 1. Caller drops days > horizon."""
    return max(1, (d - as_of).days)


def _recurring_dates(item: Recurring, as_of: date, horizon: int) -> Iterator[date]:
    if item.period_days <= 0:
        raise ValueError("recurring period_days must be positive")
    behind = (as_of - item.next_expected).days
    steps = behind // item.period_days + 1 if behind >= 0 else 0
    current = item.next_expected + timedelta(days=steps * item.period_days)
    while (current - as_of).days <= horizon:
        yield current
        current += timedelta(days=item.period_days)


def _fixed_line_dates(line: FixedLine, as_of: date, horizon: int) -> Iterator[date]:
    if line.cadence == "once":
        if line.next_date > as_of and (line.next_date - as_of).days <= horizon:
            yield line.next_date
        return
    months = CADENCE_MONTHS[line.cadence]
    n = 0
    current = line.next_date
    while (current - as_of).days <= horizon:
        if current > as_of:
            yield current
        n += 1
        current = add_months(line.next_date, n * months)


def _signed(amount: Decimal, direction: Direction) -> int:
    paise = to_paise(amount)
    return paise if direction == "inflow" else -paise


def weighted(amount: Decimal, factor: Decimal) -> Decimal:
    return (amount * factor).quantize(PAISE, rounding=ROUND_HALF_UP)


def _scheduled_events(inputs: ForecastInputs, horizon: int) -> list[_Event]:
    """Everything that is deterministic in every Monte Carlo path: AP on due date,
    fixed lines, statutory."""
    as_of = inputs.opening.as_of
    events = [_Event(_day_index(a.due_date, as_of), -to_paise(a.amount)) for a in inputs.ap]
    events += [_Event(_day_index(s.date, as_of), -to_paise(s.amount)) for s in inputs.statutory]
    for line in inputs.fixed_lines:
        events += [
            _Event(_day_index(d, as_of), _signed(line.amount, line.direction))
            for d in _fixed_line_dates(line, as_of, horizon)
        ]
    return [e for e in events if e.day <= horizon]


def _recurring_events(inputs: ForecastInputs, horizon: int) -> list[_Event]:
    as_of = inputs.opening.as_of
    events: list[_Event] = []
    for item in inputs.recurring:
        paise = -to_paise(weighted(item.amount, item.weight))
        events += [
            _Event(_day_index(d, as_of), paise) for d in _recurring_dates(item, as_of, horizon)
        ]
    return events


def _deterministic_events(inputs: ForecastInputs, horizon: int) -> list[_Event]:
    as_of = inputs.opening.as_of
    events = _scheduled_events(inputs, horizon) + _recurring_events(inputs, horizon)
    events += [_Event(_day_index(a.due_date, as_of), to_paise(a.amount)) for a in inputs.ar]
    events += [
        _Event(_day_index(e.expected_date, as_of), to_paise(weighted(e.amount, e.probability)))
        for e in inputs.expected
    ]
    return [e for e in events if e.day <= horizon]


def deterministic_path(inputs: ForecastInputs, horizon: int) -> tuple[Decimal, ...]:
    """Cumulative cash per horizon day with everything on its due date. Exact Decimal."""
    daily = [0] * (horizon + 1)
    for e in _deterministic_events(inputs, horizon):
        daily[e.day] += e.paise
    running = to_paise(inputs.opening.amount)
    out: list[Decimal] = []
    for k in range(1, horizon + 1):
        running += daily[k]
        out.append(from_paise(running))
    return tuple(out)


class _Simulator:
    """Accumulates signed paise into a (n_paths, horizon + 1) matrix; column 0 unused."""

    def __init__(self, inputs: ForecastInputs, horizon: int, n_paths: int, seed: int) -> None:
        self.inputs = inputs
        self.horizon = horizon
        self.n_paths = n_paths
        self.rng = np.random.default_rng(seed)
        self.flows: IntArray = np.zeros((n_paths, horizon + 1), dtype=np.int64)
        self.path_idx: IntArray = np.arange(n_paths, dtype=np.int64)

    def add_all_paths(self, day: int, paise: int) -> None:
        self.flows[:, day] += paise

    def add_per_path(self, days: IntArray, paise: int, alive: BoolArray) -> None:
        mask = alive & (days <= self.horizon)
        np.add.at(self.flows, (self.path_idx[mask], days[mask]), paise)

    def sample_days(self, dist: Distribution | None, min_exclusive: int | None) -> IntArray:
        """Uniform draw over the distribution's samples; when the invoice is already
        `min_exclusive` days late only samples beyond that are feasible."""
        if dist is None:
            return np.zeros(self.n_paths, dtype=np.int64)
        samples = np.asarray(dist.samples, dtype=np.int64)
        if min_exclusive is not None:
            feasible = samples[samples > min_exclusive]
            if feasible.size == 0:
                # Nothing in history is this late: assume settlement tomorrow.
                return np.full(self.n_paths, min_exclusive + 1, dtype=np.int64)
            samples = feasible
        picks = self.rng.integers(0, samples.size, size=self.n_paths)
        return samples[picks]

    def add_receivable(self, item: ARItem) -> None:
        as_of = self.inputs.opening.as_of
        dist = self.inputs.distributions.get(item.party_key)
        late_so_far = (as_of - item.due_date).days
        days = self.sample_days(dist, late_so_far if late_so_far >= 0 else None)
        due_offset = (item.due_date - as_of).days
        pay_day = np.maximum(due_offset + days, 1)
        p_nonpay = dist.non_payment_probability if dist is not None else 0.0
        alive: BoolArray = self.rng.random(self.n_paths) >= p_nonpay
        self.add_per_path(pay_day, to_paise(item.amount), alive)

    def add_expected(self, item: Expected) -> None:
        as_of = self.inputs.opening.as_of
        dist = self.inputs.distributions.get(item.party_key) if item.party_key else None
        days = self.sample_days(dist, None)
        pay_day = np.maximum((item.expected_date - as_of).days + days, 1)
        threshold = np.float64(item.probability)
        happens: BoolArray = self.rng.random(self.n_paths) < threshold
        self.add_per_path(pay_day, to_paise(item.amount), happens)

    def add_recurring(self, item: Recurring) -> None:
        as_of = self.inputs.opening.as_of
        paise = -to_paise(weighted(item.amount, item.weight))
        always: BoolArray = np.ones(self.n_paths, dtype=np.bool_)
        for occurrence in _recurring_dates(item, as_of, self.horizon + RECURRING_JITTER_DAYS):
            jitter = self.rng.integers(
                -RECURRING_JITTER_DAYS, RECURRING_JITTER_DAYS + 1, size=self.n_paths
            )
            day = np.maximum((occurrence - as_of).days + jitter, 1)
            self.add_per_path(day, paise, always)

    def cumulative(self) -> IntArray:
        for e in _scheduled_events(self.inputs, self.horizon):
            self.add_all_paths(e.day, e.paise)
        for ar in self.inputs.ar:
            self.add_receivable(ar)
        for ex in self.inputs.expected:
            self.add_expected(ex)
        for rec in self.inputs.recurring:
            self.add_recurring(rec)
        opening = to_paise(self.inputs.opening.amount)
        cum: IntArray = np.cumsum(self.flows[:, 1:], axis=1) + opening
        return cum


def _bands(cum: IntArray) -> tuple[list[Decimal], list[Decimal], list[Decimal]]:
    # inverted_cdf returns actual sample values, so int64 paise survive; astype is a no-op cast.
    q: IntArray = np.quantile(cum, BAND_QUANTILES, axis=0, method="inverted_cdf").astype(np.int64)
    return (
        [from_paise(int(v)) for v in q[0]],
        [from_paise(int(v)) for v in q[1]],
        [from_paise(int(v)) for v in q[2]],
    )


def _runway(points: Sequence[DayPoint]) -> date | None:
    for p in points:
        floor = p.p10 if p.p10 is not None else p.deterministic
        if floor < 0:
            return p.date
    return None


def run(
    inputs: ForecastInputs,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    n_paths: int = DEFAULT_N_PATHS,
    seed: int = 0,
) -> ForecastResult:
    """n_paths == 0 yields the deterministic path only (bands None): the under-90-days
    honesty rule (§8.1)."""
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    if n_paths < 0:
        raise ValueError("n_paths must be non-negative")
    as_of = inputs.opening.as_of
    det = deterministic_path(inputs, horizon_days)
    if n_paths:
        p10, p50, p90 = _bands(_Simulator(inputs, horizon_days, n_paths, seed).cumulative())
    else:
        p10 = p50 = p90 = [None] * horizon_days  # type: ignore[list-item]
    points = tuple(
        DayPoint(as_of + timedelta(days=k + 1), det[k], p10[k], p50[k], p90[k])
        for k in range(horizon_days)
    )
    return ForecastResult(as_of, horizon_days, n_paths, seed, points, _runway(points))
