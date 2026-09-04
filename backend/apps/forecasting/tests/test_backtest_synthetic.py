"""§8.7 end to end: a synthetic 14-month history, then a real run with a rolling-origin
backtest. Prints MAPE / coverage so the calibration verdict can be reported."""

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.forecasting.domain.engine import add_months
from apps.forecasting.models import RecurringExpensePattern
from apps.forecasting.services.recurring import detect_and_persist
from apps.forecasting.services.runs import run_forecast
from apps.forecasting.tests.helpers import confirmed_invoice, pay
from apps.invoices.factories import LineFactory
from apps.parties.factories import CategoryFactory, PartyFactory
from apps.payments.models import BankBalanceSnapshot

pytestmark = pytest.mark.django_db

START = date(2025, 7, 1)
MONTHS = 14
AS_OF = date(2026, 9, 1)


def build_history(org) -> None:  # type: ignore[no-untyped-def]
    rng = random.Random(42)
    customers = [
        (PartyFactory(org=org, legal_name="Prompt Ltd", payment_terms_days=30), "10000", (-3, 4)),
        (PartyFactory(org=org, legal_name="Late Ltd", payment_terms_days=30), "20000", (15, 45)),
        (PartyFactory(org=org, legal_name="Erratic Ltd", payment_terms_days=30), "50000", (-5, 70)),
    ]
    landlord = PartyFactory(org=org, legal_name="Landlord", kind="vendor")
    saas = PartyFactory(org=org, legal_name="SaaS Co", kind="vendor")
    rent_cat = CategoryFactory(org=org, name="Rent")
    for m in range(MONTHS):
        month_start = add_months(START, m)
        for party, taxable, (lo, hi) in customers:
            inv = confirmed_invoice(
                org, party, direction="outward", invoice_date=month_start, taxable=taxable
            )
            pay(inv, inv.due_date + timedelta(days=rng.randint(lo, hi)))
        # rent and SaaS are settled on the invoice date (advance rent, card auto-debit)
        rent = confirmed_invoice(
            org,
            landlord,
            direction="inward",
            invoice_date=month_start,
            taxable="25000",
            due_date=month_start,
        )
        LineFactory(invoice=rent, category=rent_cat)
        pay(rent, month_start)
        saas_day = month_start + timedelta(days=4)
        bill = confirmed_invoice(
            org, saas, direction="inward", invoice_date=saas_day, taxable="4000", due_date=saas_day
        )
        pay(bill, saas_day + timedelta(days=1))
    BankBalanceSnapshot.objects.create(org=org, date=AS_OF, balance=Decimal("500000.00"))


def test_fourteen_month_history_backtests_with_rolling_origins(org_a) -> None:  # type: ignore[no-untyped-def]
    build_history(org_a.org)
    # the owner has reviewed the recurring-pattern suggestions (rent, SaaS) and confirmed them
    assert len(detect_and_persist(org_a.org, AS_OF)) == 2
    RecurringExpensePattern.objects.for_org(org_a.org).update(user_confirmed=True)
    run = run_forecast(org_a.org, as_of=AS_OF, seed=42)
    assert run.status == "done" and run.insufficient_history is False
    assert run.history_days == (AS_OF - START).days
    assert run.backtest_n_origins is not None and run.backtest_n_origins >= 8
    assert run.backtest_mape is not None and run.backtest_coverage is not None
    assert Decimal("0") <= run.backtest_coverage <= Decimal("1")
    checkpoints = run.params["backtest"]["checkpoints"]
    assert len(checkpoints) >= 3 * (run.backtest_n_origins - 3)
    points = list(run.points.all())
    assert len(points) == 91 and all(p.p10 is not None and p.p10 <= p.p50 <= p.p90 for p in points)  # type: ignore[operator]
    print(
        f"\nBACKTEST origins={run.backtest_n_origins} checkpoints={len(checkpoints)} "
        f"MAPE={run.backtest_mape} coverage={run.backtest_coverage} "
        f"calibrated={run.params['backtest']['is_calibrated']} runway={run.runway_date}"
    )
    for days in (28, 56, 91):
        rows = [c for c in checkpoints if c["days_ahead"] == days]
        covered = sum(1 for c in rows if c["is_covered"])
        apes = [Decimal(c["abs_pct_error"]) for c in rows if c["abs_pct_error"] is not None]
        mape = sum(apes) / len(apes) if apes else None
        print(f"  {days:>2}d: n={len(rows)} covered={covered} mape={mape}")
    for c in checkpoints:
        print(
            f"  {c['as_of']} +{c['days_ahead']:>2}d actual={c['actual']:>11} "
            f"p10={c['p10']:>11} p50={c['p50']:>11} p90={c['p90']:>11} covered={c['is_covered']}"
        )
