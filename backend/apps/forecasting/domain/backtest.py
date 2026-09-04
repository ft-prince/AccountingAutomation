"""Rolling-origin backtest (PROJECT_SPECS §8.7).

The caller prepares one BacktestOrigin per month-end with >= 90 days of prior history:
the engine inputs as-of that date and the actual cumulative cash at each checkpoint
(28 / 56 / 91 days = 4 / 8 / 13 weeks). We report MAPE of P50 against actual and the
share of actuals inside P10-P90; bands are calibrated when coverage is within 75-90%.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from apps.forecasting.domain.engine import DayPoint, ForecastInputs, run

CHECKPOINT_DAYS: tuple[int, ...] = (28, 56, 91)
COVERAGE_TARGET_LOW = Decimal("0.75")
COVERAGE_TARGET_HIGH = Decimal("0.90")
BACKTEST_N_PATHS = 500
FOUR_DP = Decimal("0.0001")


@dataclass(frozen=True)
class BacktestOrigin:
    inputs: ForecastInputs
    actual_cash: Mapping[int, Decimal]  # days ahead -> actual cumulative cash


@dataclass(frozen=True)
class CheckpointResult:
    as_of: date
    days_ahead: int
    actual: Decimal
    p10: Decimal
    p50: Decimal
    p90: Decimal
    abs_pct_error: Decimal | None
    is_covered: bool


@dataclass(frozen=True)
class BacktestResult:
    n_origins: int
    mape: Decimal | None
    coverage: Decimal | None
    is_calibrated: bool | None
    checkpoints: tuple[CheckpointResult, ...]


def _checkpoint(as_of: date, days: int, actual: Decimal, point: DayPoint) -> CheckpointResult:
    assert point.p10 is not None and point.p50 is not None and point.p90 is not None
    ape = (
        (abs(actual - point.p50) / abs(actual)).quantize(FOUR_DP, rounding=ROUND_HALF_UP)
        if actual != 0
        else None
    )
    return CheckpointResult(
        as_of=as_of,
        days_ahead=days,
        actual=actual,
        p10=point.p10,
        p50=point.p50,
        p90=point.p90,
        abs_pct_error=ape,
        is_covered=point.p10 <= actual <= point.p90,
    )


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return (sum(values, Decimal(0)) / len(values)).quantize(FOUR_DP, rounding=ROUND_HALF_UP)


def backtest(
    origins: Sequence[BacktestOrigin],
    n_paths: int = BACKTEST_N_PATHS,
    seed: int = 0,
    checkpoints: Sequence[int] = CHECKPOINT_DAYS,
) -> BacktestResult:
    if n_paths <= 0:
        raise ValueError("a backtest needs Monte Carlo bands; n_paths must be positive")
    horizon = max(checkpoints)
    results: list[CheckpointResult] = []
    for origin in origins:
        wanted = [d for d in checkpoints if d in origin.actual_cash]
        if not wanted:
            continue
        points = run(origin.inputs, horizon_days=horizon, n_paths=n_paths, seed=seed).points
        as_of = origin.inputs.opening.as_of
        results += [_checkpoint(as_of, d, origin.actual_cash[d], points[d - 1]) for d in wanted]
    apes = [c.abs_pct_error for c in results if c.abs_pct_error is not None]
    coverage = _mean([Decimal(int(c.is_covered)) for c in results])
    calibrated = (
        COVERAGE_TARGET_LOW <= coverage <= COVERAGE_TARGET_HIGH if coverage is not None else None
    )
    return BacktestResult(
        n_origins=len(origins),
        mape=_mean(apes),
        coverage=coverage,
        is_calibrated=calibrated,
        checkpoints=tuple(results),
    )
