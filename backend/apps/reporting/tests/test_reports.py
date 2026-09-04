import time
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.models import Sum

from apps.accounts.models import Organization, OrgMembership
from apps.invoices.models import Invoice
from apps.parties.models import Party
from apps.payments.models import PaymentAllocation
from apps.reporting.services import REPORTS, Period, ar_aging, pnl, summary, tax_liability

pytestmark = pytest.mark.django_db
D = Decimal
TODAY = date(2026, 9, 4)


@pytest.fixture(scope="module")
def demo(django_db_setup, django_db_blocker):  # type: ignore[no-untyped-def]
    with django_db_blocker.unblock():
        out = StringIO()
        call_command("generate_demo_data", today=TODAY.isoformat(), stdout=out)
        org = Organization.objects.get(name="Nexren Demo")
        yield org, out.getvalue()
        from apps.payments.models import BankAccount, Payment

        Payment.objects.filter(org=org).delete()
        Invoice.objects.filter(org=org).delete()
        BankAccount.objects.filter(org=org).delete()
        Party.objects.filter(org=org).delete()
        org.delete()


@pytest.fixture
def demo_client(demo):  # type: ignore[no-untyped-def]
    from rest_framework.test import APIClient

    org, _ = demo
    c = APIClient()
    c.force_login(OrgMembership.objects.get(org=org).user)
    return c


def test_demo_data_shape(demo) -> None:  # type: ignore[no-untyped-def]
    org, out = demo
    n = Invoice.objects.filter(org=org).count()
    assert 500 <= n <= 900, out
    assert Party.objects.filter(org=org).count() == 30
    assert Invoice.objects.filter(org=org, status="needs_review").count() >= 10
    assert Invoice.objects.filter(org=org, status="duplicate").count() >= 1
    assert Invoice.objects.filter(org=org, payment_status="overdue").exists()


@pytest.mark.parametrize("name", sorted(REPORTS))
def test_every_report_states_its_basis_and_runs_under_300ms(demo_client, name) -> None:  # type: ignore[no-untyped-def]
    demo_client.get(
        "/api/reports/summary"
    )  # warm-up: first request pays for resolver/middleware imports
    t0 = time.perf_counter()
    r = demo_client.get(f"/api/reports/{name}?fy=2026-27")
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, r.content[:300]
    meta = r.json()["meta"]
    assert set(meta) >= {"fy", "period", "basis", "invoice_count", "pending_count"}
    assert meta["fy"] == "2026-27" and meta["basis"] == "accrual"
    assert elapsed < 300, f"{name} took {elapsed:.0f} ms"


def test_summary_revenue_equals_sum_of_confirmed_rows(demo) -> None:  # type: ignore[no-untyped-def]
    org, _ = demo
    period = Period(date(2026, 4, 1), date(2027, 3, 31), "accrual")
    got = D(summary(org, period)["revenue"])
    expected = Invoice.objects.filter(
        org=org,
        status="confirmed",
        direction="outward",
        invoice_date__range=(period.start, period.end),
    ).aggregate(s=Sum("taxable_value"))["s"]
    assert got == expected
    # pending invoices are NOT in the total but ARE counted
    assert (
        summary(org, period)["meta"]["pending_count"]
        == Invoice.objects.filter(
            org=org, status="needs_review", invoice_date__range=(period.start, period.end)
        ).count()
    )


def test_pnl_rows_sum_to_summary(demo) -> None:  # type: ignore[no-untyped-def]
    org, _ = demo
    period = Period(date(2026, 4, 1), date(2027, 3, 31), "accrual")
    rows = pnl(org, period)["rows"]
    assert sum(D(r["revenue"]) for r in rows) == D(summary(org, period)["revenue"])
    assert sum(D(r["opex"]) + D(r["cogs"]) for r in rows) == D(summary(org, period)["expenses"])


def test_cash_basis_uses_allocations(demo) -> None:  # type: ignore[no-untyped-def]
    org, _ = demo
    period = Period(date(2026, 4, 1), date(2026, 6, 30), "cash")
    got = D(summary(org, period)["revenue"])
    allocs = PaymentAllocation.objects.filter(
        invoice__org=org,
        invoice__direction="outward",
        invoice__status="confirmed",
        payment__date__range=(period.start, period.end),
    ).select_related("invoice")
    expected = sum(
        (a.amount * a.invoice.taxable_value / a.invoice.total for a in allocs), D("0")
    ).quantize(D("0.01"))
    assert abs(got - expected) <= D("0.05")
    assert summary(org, period)["meta"]["basis"] == "cash"


def test_ar_aging_buckets_sum_to_open_receivables(demo) -> None:  # type: ignore[no-untyped-def]
    org, _ = demo
    period = Period(date(2026, 4, 1), TODAY, "accrual")
    rep = ar_aging(org, period, as_of=TODAY)
    open_q = Invoice.objects.filter(org=org, status="confirmed", direction="outward").exclude(
        payment_status__in=["paid", "written_off"]
    )
    expected = sum((i.total - i.amount_paid for i in open_q), D("0"))
    assert D(rep["totals"]["total"]) == expected
    assert sum(D(rep["totals"][b]) for b in ("0-30", "31-60", "61-90", "90+")) == expected
    assert sum(D(r["total"]) for r in rep["rows"]) == expected
    assert D(rep["totals"]["90+"]) > 0  # the non-payer


def test_tax_liability_upcoming_due_dates(demo) -> None:  # type: ignore[no-untyped-def]
    org, _ = demo
    rep = tax_liability(org, Period(date(2026, 4, 1), date(2027, 3, 31), "accrual"), today=TODAY)
    aug = next(r for r in rep["rows"] if r["period"] == "2026-08")
    assert aug["gstr1_due"] == "2026-09-11" and aug["gstr3b_due"] == "2026-09-20"
    assert rep["upcoming"][0]["due"] >= TODAY.isoformat()
    assert D(aug["net_payable"]) == D(aug["output_tax"]) - D(aug["eligible_itc"])
    assert D(rep["totals"]["blocked_itc"]) > 0  # Meals & Entertainment


def test_bad_params_are_400_and_unknown_report_404(demo_client) -> None:  # type: ignore[no-untyped-def]
    assert demo_client.get("/api/reports/summary?basis=magic").status_code == 400
    assert demo_client.get("/api/reports/summary?from=2026-05-01&to=2026-04-01").status_code == 400
    assert demo_client.get("/api/reports/nope").status_code == 404


def test_reports_are_org_scoped(client_b) -> None:  # type: ignore[no-untyped-def]
    r = client_b.get("/api/reports/summary")
    assert r.status_code == 200 and r.json()["revenue"] == "0"
