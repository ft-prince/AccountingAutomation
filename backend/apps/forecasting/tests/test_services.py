"""Input assembly, persistence and run orchestration against the database."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.forecasting.models import ForecastRun, RecurringExpensePattern
from apps.forecasting.services import inputs as svc
from apps.forecasting.services.backtest import actual_net_flow, month_ends_between
from apps.forecasting.services.recurring import detect_and_persist
from apps.forecasting.services.runs import (
    TRIGGER_NIGHTLY,
    RateLimitedError,
    latest_run,
    run_forecast,
)
from apps.forecasting.tests.helpers import confirmed_invoice, pay
from apps.invoices.factories import LineFactory
from apps.parties.factories import CategoryFactory, PartyFactory
from apps.payments.factories import BankAccountFactory, TransactionFactory
from apps.payments.models import BankBalanceSnapshot

pytestmark = pytest.mark.django_db
AS_OF = date(2026, 9, 1)


def test_under_90_days_run_stores_null_bands_and_flags_insufficient_history(org_a) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_a.org)
    confirmed_invoice(
        org_a.org,
        party,
        direction="outward",
        invoice_date=AS_OF - timedelta(days=30),
        taxable="10000",
    )
    run = run_forecast(org_a.org, as_of=AS_OF, seed=5)
    assert run.status == "done"
    assert run.insufficient_history is True
    assert run.history_days == 30
    assert run.seed == 5
    assert len(run.inputs_hash) == 64
    assert run.params["trigger"] == "manual" and run.params["n_paths"] == 2000
    assert run.backtest_n_origins is None and run.backtest_mape is None
    points = list(run.points.all())
    assert len(points) == 91
    assert all(p.p10 is None and p.p50 is None and p.p90 is None for p in points)
    # due = 2 Aug + 30 = 1 Sep = as_of, so the 11800 lands on horizon day 1
    assert points[0].deterministic == Decimal("11800.00")
    assert latest_run(org_a.org) == run


def test_inputs_assemble_ar_ap_outstanding_and_due_fallback(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    customer = PartyFactory(org=org, payment_terms_days=45)
    vendor = PartyFactory(org=org)
    partial = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 8, 1), taxable="10000"
    )
    pay(partial, date(2026, 8, 20), Decimal("1800.00"))
    settled = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 7, 1), taxable="10000"
    )
    pay(settled, date(2026, 8, 5))
    no_due = confirmed_invoice(
        org,
        customer,
        direction="outward",
        invoice_date=date(2026, 8, 10),
        taxable="1000",
        due_date=None,
    )
    bill = confirmed_invoice(
        org, vendor, direction="inward", invoice_date=date(2026, 8, 15), taxable="5000"
    )
    confirmed_invoice(
        org,
        vendor,
        direction="inward",
        invoice_date=date(2026, 8, 16),
        taxable="5000",
        status="needs_review",
    )
    future = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 9, 5), taxable="1"
    )

    fi = svc.assemble_inputs(org, AS_OF)
    ar = {a.amount: a for a in fi.ar}
    assert set(ar) == {Decimal("10000.00"), Decimal("1180.00")}
    assert ar[Decimal("1180.00")].due_date == no_due.invoice_date + timedelta(days=45)
    assert [a.amount for a in fi.ap] == [Decimal("5900.00")]
    assert fi.ap[0].party_key == str(vendor.pk) and fi.ap[0].due_date == bill.due_date
    assert future.pk not in {
        a.party_key for a in fi.ar
    }  # dated after as_of: not part of the books yet
    assert fi.opening.amount == Decimal("0") and fi.opening.as_of == AS_OF
    assert svc.history_days(org, AS_OF) == (AS_OF - date(2026, 7, 1)).days
    assert len(svc.inputs_hash(fi)) == 64 and svc.inputs_hash(fi) == svc.inputs_hash(fi)


def test_distribution_is_built_from_allocation_dates_relative_to_due(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    customer = PartyFactory(org=org)
    for offset, paid_after in ((1, 5), (2, 10), (3, 15)):
        inv = confirmed_invoice(
            org, customer, direction="outward", invoice_date=date(2026, 1, offset), taxable="100"
        )
        pay(inv, inv.due_date + timedelta(days=paid_after))
    open_late = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 1, 10), taxable="100"
    )
    assert open_late.due_date is not None
    fi = svc.assemble_inputs(org, AS_OF)
    dist = fi.distributions[str(customer.pk)]
    assert dist.source == "party"
    assert dist.samples == (5, 10, 15)
    assert dist.non_payment_probability == 0.25  # one of four is > 120 days late (still open)


def test_opening_cash_uses_newest_observation_per_account_plus_org_snapshots(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    acct = BankAccountFactory(org=org)
    BankBalanceSnapshot.objects.create(
        org=org, bank_account=acct, date=date(2026, 8, 30), balance=Decimal("1000")
    )
    TransactionFactory(bank_account=acct, date=date(2026, 8, 31), balance_after=Decimal("2000"))
    TransactionFactory(
        bank_account=acct, date=date(2026, 9, 5), balance_after=Decimal("9999")
    )  # after as_of
    BankBalanceSnapshot.objects.create(
        org=org, bank_account=None, date=date(2026, 8, 1), balance=Decimal("500")
    )
    assert svc.opening_cash(org, AS_OF) == Decimal("2500")
    BankBalanceSnapshot.objects.create(
        org=org, bank_account=acct, date=date(2026, 8, 31), balance=Decimal("3000")
    )
    assert svc.opening_cash(org, AS_OF) == Decimal("3500")  # tie on date: manual snapshot wins
    empty = BankAccountFactory(org=org)
    assert svc.opening_cash(org, AS_OF) == Decimal("3500")
    TransactionFactory(bank_account=empty, date=date(2026, 8, 1), balance_after=Decimal("10"))
    assert svc.opening_cash(org, AS_OF) == Decimal("3510")


def test_statutory_gstr3b_net_payable_per_open_period(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    party = PartyFactory(org=org)
    confirmed_invoice(
        org, party, direction="outward", invoice_date=date(2026, 8, 5), taxable="10000"
    )  # tax 1800
    confirmed_invoice(
        org, party, direction="inward", invoice_date=date(2026, 8, 6), taxable="5000"
    )  # ITC 900
    confirmed_invoice(
        org,
        party,
        direction="inward",
        invoice_date=date(2026, 8, 7),
        taxable="2000",
        itc_eligible=False,
    )
    confirmed_invoice(
        org, party, direction="outward", invoice_date=date(2026, 7, 5), taxable="10000"
    )  # due 20 Aug: past
    confirmed_invoice(
        org, party, direction="inward", invoice_date=date(2026, 6, 5), taxable="90000"
    )  # negative net
    out = svc.statutory_outflows(org, AS_OF)
    assert [(s.amount, s.date) for s in out] == [(Decimal("900.00"), date(2026, 9, 20))]


def test_recurring_patterns_are_persisted_and_user_decisions_survive_rerun(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    landlord = PartyFactory(org=org)
    rent_cat = CategoryFactory(org=org, name="Rent")
    for month in (3, 4, 5, 6):
        inv = confirmed_invoice(
            org, landlord, direction="inward", invoice_date=date(2026, month, 1), taxable="25000"
        )
        LineFactory(invoice=inv, category=rent_cat, taxable_value=Decimal("25000"))
    confirmed_invoice(
        org,
        PartyFactory(org=org),
        direction="inward",
        invoice_date=date(2026, 5, 9),
        taxable="80000",
    )

    rows = detect_and_persist(org, AS_OF)
    assert len(rows) == 1
    row = rows[0]
    assert row.party == landlord and row.category == rent_cat
    assert row.amount_p50 == Decimal("29500.00") and row.occurrences == 4
    assert row.user_confirmed is None and row.next_expected == date(2026, 7, 2)
    assert [r.weight for r in svc.stored_recurring(org)] == [Decimal("0.7")]

    row.user_confirmed = True
    row.save()
    again = detect_and_persist(org, AS_OF)
    assert RecurringExpensePattern.objects.for_org(org).count() == 1
    assert again[0].pk == row.pk and again[0].user_confirmed is True
    assert [r.weight for r in svc.stored_recurring(org)] == [Decimal("1")]

    row.user_confirmed = False
    row.save()
    assert svc.stored_recurring(org) == ()


def test_manual_runs_are_rate_limited_but_nightly_runs_are_not(org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    run_forecast(org_a.org, as_of=AS_OF)
    with pytest.raises(RateLimitedError) as exc:
        run_forecast(org_a.org, as_of=AS_OF)
    assert 0 < exc.value.retry_after_seconds <= 600
    run_forecast(org_a.org, as_of=AS_OF, trigger=TRIGGER_NIGHTLY)
    run_forecast(org_b.org, as_of=AS_OF)  # another org is unaffected
    assert ForecastRun.objects.for_org(org_a.org).count() == 2


def test_failed_run_is_recorded_with_a_reason(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("bank feed unavailable")

    monkeypatch.setattr("apps.forecasting.services.runs.assemble_inputs", boom)
    with pytest.raises(RuntimeError):
        run_forecast(org_a.org, as_of=AS_OF)
    run = ForecastRun.objects.for_org(org_a.org).get()
    assert run.status == "failed"
    assert run.error == "RuntimeError: bank feed unavailable"
    assert latest_run(org_a.org) is None


def test_history_days_is_zero_without_confirmed_invoices(org_a) -> None:  # type: ignore[no-untyped-def]
    assert svc.history_days(org_a.org, AS_OF) == 0
    assert svc.assemble_inputs(org_a.org, AS_OF).ar == ()


def test_actual_net_flow_counts_known_receipts_and_all_payments_made(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    customer, vendor = PartyFactory(org=org), PartyFactory(org=org)
    origin = date(2026, 6, 30)
    known = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 6, 10), taxable="10000"
    )
    pay(known, date(2026, 7, 15))  # +11800
    unknown = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 7, 1), taxable="10000"
    )
    pay(unknown, date(2026, 7, 20))  # raised after the origin: not forecastable, excluded
    before = confirmed_invoice(
        org, customer, direction="outward", invoice_date=date(2026, 5, 1), taxable="10000"
    )
    pay(before, origin)  # paid on the origin day itself: outside (origin, end]
    bill = confirmed_invoice(
        org, vendor, direction="inward", invoice_date=date(2026, 7, 3), taxable="1000"
    )
    pay(bill, date(2026, 7, 10))  # -1180: invoiced after origin but vendor is recurring
    late_bill = confirmed_invoice(
        org, vendor, direction="inward", invoice_date=date(2026, 7, 3), taxable="1000"
    )
    pay(late_bill, date(2026, 9, 1))  # after the window
    assert actual_net_flow(org, origin, date(2026, 7, 31), {str(vendor.pk)}) == Decimal("10620.00")
    assert actual_net_flow(org, date(2027, 1, 1), date(2027, 2, 1), set()) == Decimal("0")


def test_month_ends_between() -> None:
    assert month_ends_between(date(2026, 1, 15), date(2026, 3, 31)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert month_ends_between(date(2026, 2, 1), date(2026, 2, 27)) == []


def test_backtest_inputs_apply_todays_pattern_decisions(org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    landlord, saas = PartyFactory(org=org), PartyFactory(org=org)
    for month in (3, 4, 5, 6):
        confirmed_invoice(
            org, landlord, direction="inward", invoice_date=date(2026, month, 1), taxable="25000"
        )
        confirmed_invoice(
            org, saas, direction="inward", invoice_date=date(2026, month, 5), taxable="4000"
        )
    unknown = svc.assemble_inputs(org, AS_OF, for_backtest=True)
    assert sorted(r.weight for r in unknown.recurring) == [Decimal("0.7"), Decimal("0.7")]
    assert unknown.opening.amount == Decimal("0") and unknown.fixed_lines == ()

    rows = {r.party_id: r for r in detect_and_persist(org, AS_OF)}
    rows[landlord.pk].user_confirmed = True
    rows[landlord.pk].save()
    rows[saas.pk].user_confirmed = False
    rows[saas.pk].save()
    decided = svc.assemble_inputs(org, AS_OF, for_backtest=True)
    assert [r.weight for r in decided.recurring] == [Decimal("1")]
    assert decided.recurring[0].amount == Decimal("29500.00")
