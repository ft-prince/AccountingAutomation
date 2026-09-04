"""§8.7 rolling-origin backtest metrics."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.forecasting.domain.backtest import (
    CHECKPOINT_DAYS,
    BacktestOrigin,
    backtest,
)
from apps.forecasting.domain.distributions import Distribution
from apps.forecasting.domain.engine import APItem, ARItem, ForecastInputs, OpeningCash, run

AS_OF = date(2026, 1, 31)


def _inputs(spread: Distribution) -> ForecastInputs:
    return ForecastInputs(
        opening=OpeningCash(Decimal("1000.00"), AS_OF),
        ar=tuple(
            ARItem("acme", Decimal("100.00"), AS_OF + timedelta(days=d)) for d in range(1, 90, 5)
        ),
        ap=(APItem(Decimal("300.00"), AS_OF + timedelta(days=40)),),
        distributions={"acme": spread},
    )


def test_perfect_foresight_gives_zero_mape_and_full_coverage() -> None:
    inputs = _inputs(Distribution((0,), 0.0, "party"))
    det = run(inputs, horizon_days=91, n_paths=0, seed=0).points
    actual = {d: det[d - 1].deterministic for d in CHECKPOINT_DAYS}
    result = backtest([BacktestOrigin(inputs, actual)], n_paths=20, seed=0)
    assert result.n_origins == 1
    assert result.mape == Decimal("0.0000")
    assert result.coverage == Decimal("1.0000")
    assert result.is_calibrated is False  # 100% coverage means bands are too wide
    assert len(result.checkpoints) == 3
    assert all(c.abs_pct_error == Decimal("0.0000") for c in result.checkpoints)


def test_mape_and_coverage_are_averaged_over_checkpoints() -> None:
    inputs = _inputs(Distribution((0, 5, 20, 45), 0.05, "party"))
    bands = run(inputs, horizon_days=91, n_paths=200, seed=3).points
    inside = {d: bands[d - 1].p50 for d in (28, 56)}
    outside = {91: bands[90].p90 + Decimal("1000")}  # type: ignore[operator]
    actual = {**inside, **outside}  # type: ignore[dict-item]
    result = backtest([BacktestOrigin(inputs, actual)], n_paths=200, seed=3)
    assert result.coverage == Decimal("0.6667")
    assert result.is_calibrated is False
    assert result.mape is not None and result.mape > 0
    assert [c.is_covered for c in result.checkpoints] == [True, True, False]


def test_zero_actual_is_skipped_for_mape_and_missing_checkpoints_are_ignored() -> None:
    inputs = _inputs(Distribution((0,), 0.0, "party"))
    result = backtest([BacktestOrigin(inputs, {28: Decimal("0")})], n_paths=10, seed=0)
    assert result.mape is None
    assert result.coverage == Decimal("0.0000")
    assert len(result.checkpoints) == 1


def test_no_origins_yields_no_metrics() -> None:
    empty = backtest([], n_paths=10, seed=0)
    no_actuals = backtest([BacktestOrigin(_inputs(Distribution((0,), 0.0, "party")), {})])
    assert empty.n_origins == 0 and no_actuals.n_origins == 1
    for result in (empty, no_actuals):
        assert result.mape is None and result.coverage is None and result.is_calibrated is None
        assert result.checkpoints == ()


def test_calibrated_when_coverage_within_target() -> None:
    inputs = _inputs(Distribution((0,), 0.0, "party"))
    det = run(inputs, horizon_days=91, n_paths=0, seed=0).points
    good = {d: det[d - 1].deterministic for d in CHECKPOINT_DAYS}
    bad = {**good, 91: Decimal("-99999")}
    origins = [BacktestOrigin(inputs, good)] * 3 + [BacktestOrigin(inputs, bad)]
    result = backtest(origins, n_paths=10, seed=0)
    assert result.n_origins == 4
    assert result.coverage == Decimal("0.9167")
    assert result.is_calibrated is False
    origins = [BacktestOrigin(inputs, good)] * 2 + [BacktestOrigin(inputs, bad)] * 2
    result = backtest(origins, n_paths=10, seed=0)
    assert result.coverage == Decimal("0.8333")
    assert result.is_calibrated is True


def test_bands_are_mandatory_for_a_backtest() -> None:
    with pytest.raises(ValueError):
        backtest([], n_paths=0)
