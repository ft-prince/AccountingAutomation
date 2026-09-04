from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.documents.tests.fakes import FakeAnthropic
from apps.forecasting.domain.narrative import check_bullets, numbers_in
from apps.forecasting.models import ForecastPoint, ForecastRun
from apps.forecasting.services.narrative import aggregates_for, generate_narrative

pytestmark = pytest.mark.django_db


def test_numbers_in_normalises() -> None:
    assert numbers_in("₹12,34,567.89 by 2026-09-30 and 3 invoices") == {
        "1234567.89",
        "2026",
        "09",
        "30",
        "3",
    }
    assert numbers_in("no digits") == set()


def test_check_bullets_rejects_invented_numbers() -> None:
    allowed = {"1234567.89", "82.00"}
    r = check_bullets(
        ["Cash 12,34,567.89", "Coverage 82.00%", "Invented 99.5", "ok", "fine"], allowed
    )
    assert [b for b, _ in r.rejected] == ["Invented 99.5"] and r.rejected[0][1] == "99.5"
    assert not r.ok
    good = check_bullets(["a", "b", "c", "d", "e 82.00"], allowed)
    assert good.ok and len(good.accepted) == 5
    assert not check_bullets(["only", "four", "bullets", "here"], allowed).ok


def _run(org):  # type: ignore[no-untyped-def]
    run = ForecastRun.objects.create(
        org=org,
        as_of=date(2026, 9, 4),
        horizon_days=91,
        seed=1,
        status="done",
        backtest_coverage=Decimal("0.8200"),
    )
    for i in range(35):
        ForecastPoint.objects.create(
            run=run,
            date=date(2026, 9, 5) + timedelta(days=i),
            p10=Decimal("100000") - i,
            p50=Decimal("150000"),
            p90=Decimal("200000"),
            deterministic=Decimal("120000"),
        )
    return run


def test_generate_narrative_stores_accepted_and_labels_source(org_a) -> None:  # type: ignore[no-untyped-def]
    run = _run(org_a.org)
    agg = aggregates_for(
        run,
        drivers=[
            {"label": "Tata Steel", "amount": "450000.00", "direction": "inflow"},
            {"label": "Rent", "amount": "85000.00", "direction": "outflow"},
        ],
        high_risk=["Vedanta"],
    )
    assert agg["day30_p50"] == "150,000.00" and agg["backtest_coverage_pct"] == "82.00"
    bullets = [
        "Tata Steel brings 450,000.00; rent takes 85,000.00.",
        "Vedanta is high risk.",
        "P10 on day 30 is 99,971.00.",
        "Chase Vedanta this week.",
        "Bands covered 82.00% of history.",
    ]
    fake = FakeAnthropic([{"bullets": bullets}])
    assert generate_narrative(run, agg, client=fake) == "\n".join(bullets)
    assert "invoice" not in str(fake.calls[0]["messages"]).lower()  # aggregates only
    run.refresh_from_db()
    assert run.narrative and run.narrative.count("\n") == 4


def test_generate_narrative_rejects_a_bullet_with_a_new_number(org_a) -> None:  # type: ignore[no-untyped-def]
    run = _run(org_a.org)
    agg = aggregates_for(run, drivers=[], high_risk=[])
    bad = ["Cash is 150,000.00.", "Risk one.", "Risk two.", "Do this.", "We expect 7 late payers."]
    assert generate_narrative(run, agg, client=FakeAnthropic([{"bullets": bad}])) is None
    run.refresh_from_db()
    assert run.narrative is None


def test_no_api_key_means_no_narrative(org_a, settings) -> None:  # type: ignore[no-untyped-def]
    settings.ANTHROPIC_API_KEY = ""
    assert generate_narrative(_run(org_a.org), {}) is None


def test_drivers_and_narrative_endpoints(client_a, org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from apps.forecasting.services import narrative as svc

    run = _run(org_a.org)
    assert client_a.get("/api/forecast/drivers").status_code == 200
    monkeypatch.setattr(svc, "generate_narrative", lambda run, agg, client=None: "a\nb\nc\nd\ne")
    r = client_a.post(f"/api/forecast/runs/{run.id}/narrative")
    assert r.status_code == 200 and r.json()["label"] == "Generated summary"
