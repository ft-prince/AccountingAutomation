"""Scenario overlays (PROJECT_SPECS §8.4): re-run the engine, persist nothing."""

from datetime import date

from django.utils import timezone

from apps.accounts.models import Organization
from apps.forecasting.domain import engine
from apps.forecasting.domain.scenarios import apply_overrides
from apps.forecasting.models import Scenario
from apps.forecasting.services.inputs import MIN_HISTORY_DAYS, assemble_inputs, history_days


def run_scenario(
    org: Organization,
    scenario: Scenario,
    *,
    horizon_days: int,
    seed: int,
    as_of: date | None = None,
) -> engine.ForecastResult:
    as_of = as_of or timezone.localdate()
    inputs = apply_overrides(assemble_inputs(org, as_of), scenario.overrides)
    n_paths = 0 if history_days(org, as_of) < MIN_HISTORY_DAYS else engine.DEFAULT_N_PATHS
    return engine.run(inputs, horizon_days, n_paths, seed)
