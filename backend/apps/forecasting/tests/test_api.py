"""§10 Forecast endpoints: roles, rate limit, tenancy, payload shapes."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.forecasting.models import FixedCashflowLine, RecurringExpensePattern, Scenario
from apps.forecasting.services.runs import run_forecast
from apps.forecasting.tests.helpers import confirmed_invoice, pay
from apps.parties.factories import PartyFactory

pytestmark = pytest.mark.django_db


def test_viewer_cannot_trigger_a_run(viewer_client) -> None:  # type: ignore[no-untyped-def]
    assert viewer_client.post("/api/forecast/run", {}, format="json").status_code == 403


def test_run_then_latest_then_rate_limited(client_a) -> None:  # type: ignore[no-untyped-def]
    assert client_a.get("/api/forecast/latest").status_code == 404
    r = client_a.post("/api/forecast/run", {"horizon_days": 30, "seed": 9}, format="json")
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["status"] == "done" and body["seed"] == 9 and body["horizon_days"] == 30
    assert body["insufficient_history"] is True and len(body["points"]) == 30
    assert body["points"][0]["p10"] is None and body["points"][0]["deterministic"] == "0.00"
    assert client_a.get("/api/forecast/latest").json()["id"] == body["id"]
    assert client_a.get(f"/api/forecast/runs/{body['id']}/").json()["id"] == body["id"]
    assert client_a.get("/api/forecast/runs/").json()["results"][0]["id"] == body["id"]

    again = client_a.post("/api/forecast/run", {}, format="json")
    assert again.status_code == 429
    body = again.json()  # RFC 7807 envelope from the project's exception handler
    assert body["status"] == 429 and body["title"] and "detail" in body
    assert int(again["Retry-After"]) > 0


def test_run_validates_horizon(client_a) -> None:  # type: ignore[no-untyped-def]
    assert (
        client_a.post("/api/forecast/run", {"horizon_days": 1000}, format="json").status_code == 400
    )


def test_cross_org_run_is_404(client_a, org_b) -> None:  # type: ignore[no-untyped-def]
    run = run_forecast(org_b.org, as_of=date(2026, 9, 1))
    assert client_a.get(f"/api/forecast/runs/{run.pk}/").status_code == 404
    assert client_a.get("/api/forecast/runs/").json()["results"] == []


def test_backtest_endpoint_reports_metrics_of_latest_run(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    assert client_a.get("/api/forecast/backtest").status_code == 404
    run_forecast(org_a.org, as_of=date(2026, 9, 1))
    body = client_a.get("/api/forecast/backtest").json()
    assert body["insufficient_history"] is True
    assert body["mape"] is None and body["coverage"] is None and body["n_origins"] is None
    assert body["is_calibrated"] is None and body["checkpoints"] == []


def test_scenario_crud_validation_and_overlay_run(client_a, viewer_client, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    bad = client_a.post(
        "/api/forecast/scenarios/",
        {"name": "x", "overrides": [{"kind": "teleport"}]},
        format="json",
    )
    assert bad.status_code == 400
    assert (
        client_a.post(
            "/api/forecast/scenarios/", {"name": "x", "overrides": {}}, format="json"
        ).status_code
        == 400
    )
    party = PartyFactory(org=org_a.org)
    overrides = [
        {"kind": "delay_customer", "party": str(party.pk), "days": 10},
        {"kind": "new_hire", "amount": "80000.00", "start": "2026-10-01"},
    ]
    r = client_a.post(
        "/api/forecast/scenarios/", {"name": "hire", "overrides": overrides}, format="json"
    )
    assert r.status_code == 201, r.content
    sid = r.json()["id"]
    assert (
        viewer_client.post(
            "/api/forecast/scenarios/", {"name": "v", "overrides": []}, format="json"
        ).status_code
        == 403
    )

    run = viewer_client.post(f"/api/forecast/scenarios/{sid}/run")
    assert run.status_code == 200, run.content
    body = run.json()
    assert body["scenario"] == sid and body["base_run"] is None
    assert len(body["points"]) == 91 and body["points"][0]["p10"] is None
    assert Scenario.objects.for_org(org_a.org).count() == 1

    other = Scenario.objects.create(org=org_b.org, name="theirs", overrides=[])
    assert client_a.post(f"/api/forecast/scenarios/{other.pk}/run").status_code == 404
    assert client_a.get(f"/api/forecast/scenarios/{other.pk}/").status_code == 404


def test_scenario_run_uses_latest_run_horizon_and_seed(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    base = run_forecast(org_a.org, as_of=date(2026, 9, 1), horizon_days=14, seed=3)
    s = Scenario.objects.create(org=org_a.org, name="s", overrides=[])
    body = client_a.post(f"/api/forecast/scenarios/{s.pk}/run").json()
    assert body["base_run"] == str(base.pk) and body["horizon_days"] == 14 and body["seed"] == 3


def test_recurring_patterns_confirm_and_dismiss(client_a, viewer_client, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_a.org)
    row = RecurringExpensePattern.objects.create(
        org=org_a.org,
        party=party,
        amount_p50=Decimal("25000"),
        period_days=30,
        next_expected=date(2026, 10, 1),
    )
    listed = client_a.get("/api/forecast/recurring/").json()["results"]
    assert listed[0]["id"] == str(row.pk) and listed[0]["party_name"] == party.legal_name
    assert listed[0]["user_confirmed"] is None
    r = client_a.patch(
        f"/api/forecast/recurring/{row.pk}/", {"user_confirmed": True}, format="json"
    )
    assert r.status_code == 200 and r.json()["user_confirmed"] is True
    r = client_a.patch(
        f"/api/forecast/recurring/{row.pk}/",
        {"user_confirmed": False, "amount_p50": "24000.00"},
        format="json",
    )
    assert r.json()["user_confirmed"] is False and r.json()["amount_p50"] == "24000.00"
    assert (
        viewer_client.patch(
            f"/api/forecast/recurring/{row.pk}/", {"user_confirmed": True}, format="json"
        ).status_code
        == 403
    )
    theirs = RecurringExpensePattern.objects.create(
        org=org_b.org, amount_p50=Decimal("1"), period_days=30, next_expected=date(2026, 10, 1)
    )
    assert (
        client_a.patch(
            f"/api/forecast/recurring/{theirs.pk}/", {"user_confirmed": True}, format="json"
        ).status_code
        == 404
    )
    foreign_party = PartyFactory(org=org_b.org)
    r = client_a.post(
        "/api/forecast/recurring/",
        {
            "party": str(foreign_party.pk),
            "amount_p50": "1",
            "period_days": 30,
            "next_expected": "2026-10-01",
        },
        format="json",
    )
    assert r.status_code == 400


def test_fixed_lines_and_expected_invoices(client_a, org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    r = client_a.post(
        "/api/forecast/fixed-lines/",
        {
            "name": "payroll",
            "amount": "400000.00",
            "cadence": "monthly",
            "next_date": "2026-09-28",
            "direction": "outflow",
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    assert FixedCashflowLine.objects.for_org(org_a.org).get().amount == Decimal("400000.00")
    assert client_a.get("/api/forecast/fixed-lines/").json()["results"][0]["name"] == "payroll"
    assert (
        client_a.post(
            "/api/forecast/fixed-lines/",
            {"name": "x", "amount": "1", "cadence": "weekly", "next_date": "2026-09-28"},
            format="json",
        ).status_code
        == 400
    )

    party = PartyFactory(org=org_a.org)
    ok = client_a.post(
        "/api/forecast/expected/",
        {
            "party": str(party.pk),
            "amount": "50000.00",
            "expected_date": "2026-10-15",
            "probability": "0.60",
        },
        format="json",
    )
    assert ok.status_code == 201 and ok.json()["party_name"] == party.legal_name
    foreign = PartyFactory(org=org_b.org)
    bad = client_a.post(
        "/api/forecast/expected/",
        {
            "party": str(foreign.pk),
            "amount": "1",
            "expected_date": "2026-10-15",
            "probability": "0.5",
        },
        format="json",
    )
    assert bad.status_code == 400
    too_sure = client_a.post(
        "/api/forecast/expected/",
        {
            "party": str(party.pk),
            "amount": "1",
            "expected_date": "2026-10-15",
            "probability": "1.5",
        },
        format="json",
    )
    assert too_sure.status_code == 400


def test_risk_and_anomalies_endpoints(client_a, viewer_client, org_a) -> None:  # type: ignore[no-untyped-def]
    org = org_a.org
    today = date.today()
    prompt = PartyFactory(org=org, legal_name="Prompt Ltd", credit_limit=Decimal("100000"))
    late = PartyFactory(org=org, legal_name="Late Ltd", credit_limit=Decimal("10000"))
    for i in range(1, 5):
        a = confirmed_invoice(
            org,
            prompt,
            direction="outward",
            invoice_date=today - timedelta(days=200 - 30 * i),
            taxable="1000",
        )
        pay(a, a.due_date - timedelta(days=2))
        b = confirmed_invoice(
            org,
            late,
            direction="outward",
            invoice_date=today - timedelta(days=200 - 30 * i),
            taxable="10000",
        )
        pay(b, b.due_date + timedelta(days=60))
    confirmed_invoice(
        org, late, direction="outward", invoice_date=today - timedelta(days=70), taxable="20000"
    )
    vendor = PartyFactory(org=org, legal_name="SaaS Co")
    for i in range(1, 5):
        confirmed_invoice(
            org,
            vendor,
            direction="inward",
            invoice_date=today - timedelta(days=150 - 30 * i),
            taxable="5000",
        )
    confirmed_invoice(
        org, vendor, direction="inward", invoice_date=today - timedelta(days=5), taxable="20000"
    )
    confirmed_invoice(
        org, vendor, direction="inward", invoice_date=today - timedelta(days=4), taxable="20000"
    )

    risk = viewer_client.get("/api/forecast/risk/customers")
    assert risk.status_code == 200
    bands = {row["party_name"]: row["band"] for row in risk.json()}
    assert bands["Prompt Ltd"] == "low" and bands["Late Ltd"] == "high"
    assert risk.json()[0]["party_name"] == "Late Ltd"

    anomalies = client_a.get("/api/forecast/anomalies").json()
    kinds = {(a["party_name"], a["kind"]) for a in anomalies["expenses"]}
    assert ("SaaS Co", "amount") in kinds
    assert [d["related_invoice"] is not None for d in anomalies["duplicates"]] == [True]
    assert anomalies["concentration"]["is_top1_flagged"] is True
    assert anomalies["concentration"]["top1_party_name"] == "Late Ltd"
