"""Celery entry points. Idempotent; take IDs, not objects."""

from celery import shared_task

from apps.accounts.models import Organization
from apps.forecasting.services.runs import TRIGGER_NIGHTLY, run_forecast


@shared_task
def run_forecast_for_org(org_id: str) -> str:
    """One nightly ForecastRun for an org (PROJECT_SPECS §8.7). Not rate limited."""
    org = Organization.objects.get(pk=org_id)
    return str(run_forecast(org, trigger=TRIGGER_NIGHTLY).pk)


@shared_task
def run_nightly_forecasts() -> int:
    """Beat: fan out one run per org."""
    ids = list(Organization.objects.values_list("pk", flat=True))
    for org_id in ids:
        run_forecast_for_org.delay(str(org_id))
    return len(ids)
