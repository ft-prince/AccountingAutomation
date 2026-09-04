"""Create, execute and persist ForecastRuns (PROJECT_SPECS §8.3, §8.7)."""

from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Organization
from apps.forecasting.domain import engine
from apps.forecasting.domain.backtest import BacktestResult
from apps.forecasting.models import ForecastPoint, ForecastRun, RunStatus
from apps.forecasting.services.backtest import run_backtest
from apps.forecasting.services.inputs import (
    MIN_HISTORY_DAYS,
    assemble_inputs,
    history_days,
    inputs_hash,
)
from apps.forecasting.services.recurring import detect_and_persist

RATE_LIMIT_WINDOW = timedelta(minutes=10)
ENGINE_VERSION = "1"
TRIGGER_MANUAL = "manual"
TRIGGER_NIGHTLY = "nightly"
BACKTEST_BASIS = "allocated payments on invoices known at the origin plus recurring vendors"


class RateLimitedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


def check_rate_limit(org: Organization) -> None:
    """One on-demand run per org per RATE_LIMIT_WINDOW (§12: forecast runs are rate limited)."""
    since = timezone.now() - RATE_LIMIT_WINDOW
    recent = (
        ForecastRun.objects.for_org(org)
        .filter(params__trigger=TRIGGER_MANUAL, created_at__gte=since)
        .order_by("-created_at")
        .first()
    )
    if recent is not None:
        wait = recent.created_at + RATE_LIMIT_WINDOW - timezone.now()
        raise RateLimitedError(max(1, int(wait.total_seconds())))


def latest_run(org: Organization) -> ForecastRun | None:
    return (
        ForecastRun.objects.for_org(org)
        .filter(status=RunStatus.DONE)
        .order_by("-created_at")
        .first()
    )


def _backtest_params(result: BacktestResult) -> dict[str, Any]:
    return {
        "is_calibrated": result.is_calibrated,
        "basis": BACKTEST_BASIS,
        "checkpoints": [
            {
                "as_of": c.as_of.isoformat(),
                "days_ahead": c.days_ahead,
                "actual": str(c.actual),
                "p10": str(c.p10),
                "p50": str(c.p50),
                "p90": str(c.p90),
                "abs_pct_error": str(c.abs_pct_error) if c.abs_pct_error is not None else None,
                "is_covered": c.is_covered,
            }
            for c in result.checkpoints
        ],
    }


def _execute(run: ForecastRun, n_paths: int) -> None:
    org, as_of = run.org, run.as_of
    detect_and_persist(org, as_of)
    inputs = assemble_inputs(org, as_of)
    history = history_days(org, as_of)
    insufficient = history < MIN_HISTORY_DAYS
    result = engine.run(inputs, run.horizon_days, 0 if insufficient else n_paths, run.seed)
    bt = None if insufficient else run_backtest(org, as_of, run.seed)
    with transaction.atomic():
        ForecastPoint.objects.bulk_create(
            ForecastPoint(
                run=run, date=p.date, p10=p.p10, p50=p.p50, p90=p.p90, deterministic=p.deterministic
            )
            for p in result.points
        )
        run.inputs_hash = inputs_hash(inputs)
        run.history_days = history
        run.insufficient_history = insufficient
        run.opening_cash = inputs.opening.amount
        run.runway_date = result.runway_date
        if bt is not None:
            run.backtest_mape = bt.mape
            run.backtest_coverage = bt.coverage
            run.backtest_n_origins = bt.n_origins
            run.params = {**run.params, "backtest": _backtest_params(bt)}
        run.status = RunStatus.DONE
        run.save()


def run_forecast(
    org: Organization,
    *,
    horizon_days: int = engine.DEFAULT_HORIZON_DAYS,
    seed: int | None = None,
    trigger: str = TRIGGER_MANUAL,
    as_of: date | None = None,
    n_paths: int = engine.DEFAULT_N_PATHS,
) -> ForecastRun:
    """Synchronous; a failure is recorded on the run (status failed + reason) and re-raised."""
    as_of = as_of or timezone.localdate()
    if trigger == TRIGGER_MANUAL:
        check_rate_limit(org)
    run = ForecastRun.objects.create(
        org=org,
        as_of=as_of,
        horizon_days=horizon_days,
        seed=seed if seed is not None else as_of.toordinal(),
        status=RunStatus.RUNNING,
        params={"trigger": trigger, "n_paths": n_paths, "engine_version": ENGINE_VERSION},
    )
    try:
        _execute(run, n_paths)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = f"{type(exc).__name__}: {exc}"
        run.save(update_fields=["status", "error", "updated_at"])
        raise
    return run
