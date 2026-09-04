"""§8.7 on the shipped demo org: generate_demo_data builds ~15 months of history for
"Nexren Demo"; a real run must backtest with rolling origins and report MAPE / coverage.
Prints the metrics (run with -s) so the calibration verdict can be quoted."""

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import Organization
from apps.forecasting.domain.backtest import COVERAGE_TARGET_HIGH, COVERAGE_TARGET_LOW
from apps.forecasting.models import RecurringExpensePattern
from apps.forecasting.services.analytics import anomalies, customer_risk
from apps.forecasting.services.runs import run_forecast
from apps.invoices.models import Invoice
from apps.parties.models import Party
from apps.payments.models import BankAccount, Payment

pytestmark = pytest.mark.django_db

TODAY = date(2026, 9, 4)
SEED = 42
MIN_ORIGINS = 6
MIN_HISTORY_DAYS = 365
HORIZON_DAYS = 91


@pytest.fixture(scope="module")
def demo(django_db_setup, django_db_blocker):  # type: ignore[no-untyped-def]
    with django_db_blocker.unblock():
        out = StringIO()
        call_command("generate_demo_data", today=TODAY.isoformat(), stdout=out)
        org = Organization.objects.get(name="Nexren Demo")
        yield org
        Payment.objects.filter(org=org).delete()
        Invoice.objects.filter(org=org).delete()
        BankAccount.objects.filter(org=org).delete()
        Party.objects.filter(org=org).delete()
        org.delete()


@pytest.fixture(scope="module")
def demo_run(demo, django_db_blocker):  # type: ignore[no-untyped-def]
    with django_db_blocker.unblock():
        return run_forecast(demo, as_of=TODAY, seed=SEED)


def test_demo_run_backtests_with_rolling_origins_and_reports_calibration(demo_run) -> None:  # type: ignore[no-untyped-def]
    run = demo_run
    assert run.status == "done" and run.error == ""
    assert run.insufficient_history is False and run.history_days >= MIN_HISTORY_DAYS
    assert run.inputs_hash and len(run.inputs_hash) == 64
    assert run.params["trigger"] == "manual" and run.params["n_paths"] == 2000
    assert run.backtest_n_origins is not None and run.backtest_n_origins >= MIN_ORIGINS
    assert run.backtest_mape is not None and run.backtest_mape >= 0
    assert run.backtest_coverage is not None
    assert Decimal("0") <= run.backtest_coverage <= Decimal("1")
    bt = run.params["backtest"]
    is_calibrated = COVERAGE_TARGET_LOW <= run.backtest_coverage <= COVERAGE_TARGET_HIGH
    assert bt["is_calibrated"] is is_calibrated
    assert len(bt["checkpoints"]) >= 3 * (run.backtest_n_origins - 3)
    points = list(run.points.all())
    assert len(points) == HORIZON_DAYS
    assert all(p.p10 is not None and p.p10 <= p.p50 <= p.p90 for p in points)  # type: ignore[operator]
    print(
        f"\nDEMO BACKTEST origins={run.backtest_n_origins} checkpoints={len(bt['checkpoints'])} "
        f"MAPE={run.backtest_mape} coverage={run.backtest_coverage} "
        f"calibrated={bt['is_calibrated']} opening={run.opening_cash} runway={run.runway_date}"
    )
    for days in (28, 56, 91):
        rows = [c for c in bt["checkpoints"] if c["days_ahead"] == days]
        covered = sum(1 for c in rows if c["is_covered"])
        apes = [Decimal(c["abs_pct_error"]) for c in rows if c["abs_pct_error"] is not None]
        mape = (sum(apes) / len(apes)).quantize(Decimal("0.0001")) if apes else None
        print(f"  {days:>2}d: n={len(rows)} covered={covered} mape={mape}")
    for c in bt["checkpoints"]:
        print(
            f"  {c['as_of']} +{c['days_ahead']:>2}d actual={c['actual']:>12} "
            f"p10={c['p10']:>12} p50={c['p50']:>12} p90={c['p90']:>12} covered={c['is_covered']}"
        )


def test_demo_run_is_reproducible_for_the_same_seed_and_inputs(demo, demo_run) -> None:  # type: ignore[no-untyped-def]
    again = run_forecast(demo, as_of=TODAY, seed=SEED, trigger="nightly")
    assert again.inputs_hash == demo_run.inputs_hash
    assert again.backtest_mape == demo_run.backtest_mape
    assert again.backtest_coverage == demo_run.backtest_coverage
    first = [(p.date, p.p10, p.p50, p.p90, p.deterministic) for p in demo_run.points.all()]
    second = [(p.date, p.p10, p.p50, p.p90, p.deterministic) for p in again.points.all()]
    assert first == second


def test_demo_recurring_vendors_are_detected(demo, demo_run) -> None:  # type: ignore[no-untyped-def]
    patterns = RecurringExpensePattern.objects.for_org(demo).select_related("party")
    monthly = [p for p in patterns if 28 <= p.period_days <= 31]
    assert len(monthly) >= 3, [(p.party, p.period_days) for p in patterns]
    assert all(p.user_confirmed is None and p.occurrences >= 3 for p in patterns)


def test_demo_anomalies_and_risk_surface_the_seeded_cases(demo) -> None:  # type: ignore[no-untyped-def]
    report = anomalies(demo, TODAY)
    amount_flags = [a for a in report["expenses"] if a["kind"] == "amount"]
    assert any(a["party_name"].startswith("Google") for a in amount_flags), report["expenses"]
    assert Decimal(report["concentration"]["top1_share"]) > 0
    risk = customer_risk(demo, TODAY)
    bands = {r["band"] for r in risk}
    assert "low" in bands and ("watch" in bands or "high" in bands), risk
