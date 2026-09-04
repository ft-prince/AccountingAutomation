"""§8.3 engine: deterministic path to the paisa, seeded Monte Carlo, runway."""

import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from apps.forecasting.domain.distributions import Distribution
from apps.forecasting.domain.engine import (
    APItem,
    ARItem,
    Expected,
    FixedLine,
    ForecastInputs,
    OpeningCash,
    Recurring,
    Statutory,
    add_months,
    run,
)

FIXTURE = Path(__file__).parent / "fixtures" / "deterministic_10.csv"
AS_OF = date(2026, 9, 1)
POINT_MASS = Distribution(samples=(0,), non_payment_probability=0.0, source="terms")


def ten_invoice_inputs() -> ForecastInputs:
    """Six AR + four AP invoices, one payroll line, one unconfirmed rent pattern,
    one GSTR-3B outflow and one 60%-probable pipeline invoice."""
    ar = (
        ARItem("acme", Decimal("11800.00"), date(2026, 9, 5)),
        ARItem("beta", Decimal("23600.00"), date(2026, 9, 5)),
        ARItem("acme", Decimal("5900.00"), date(2026, 8, 20)),  # overdue -> day 1
        ARItem("gamma", Decimal("47200.00"), date(2026, 9, 15)),
        ARItem("beta", Decimal("1180.50"), date(2026, 9, 30)),
        ARItem("acme", Decimal("70800.00"), date(2026, 10, 10)),  # beyond horizon
    )
    ap = (
        APItem(Decimal("8000.00"), date(2026, 9, 3), party_key="v1"),
        APItem(Decimal("15000.25"), date(2026, 9, 15), party_key="v2"),
        APItem(Decimal("30000.00"), date(2026, 9, 25), party_key="v1"),
        APItem(Decimal("2500.00"), date(2026, 8, 30), party_key="v3"),  # overdue -> day 1
    )
    dists = {k: POINT_MASS for k in ("acme", "beta", "gamma")}
    return ForecastInputs(
        opening=OpeningCash(Decimal("100000.00"), AS_OF),
        ar=ar,
        ap=ap,
        recurring=(Recurring(Decimal("12000.00"), date(2026, 9, 10), 30, Decimal("0.7")),),
        fixed_lines=(
            FixedLine("payroll", Decimal("40000.00"), date(2026, 9, 28), "monthly", "outflow"),
        ),
        statutory=(Statutory(Decimal("6000.00"), date(2026, 9, 20)),),
        expected=(Expected(Decimal("10000.00"), date(2026, 9, 22), Decimal("0.6"), "acme"),),
        distributions=dists,
    )


def test_deterministic_path_matches_hand_computed_table_to_the_paisa() -> None:
    result = run(ten_invoice_inputs(), horizon_days=30, n_paths=0, seed=1)
    with FIXTURE.open() as fh:
        expected = [(date.fromisoformat(r["date"]), Decimal(r["cash"])) for r in csv.DictReader(fh)]
    got = [(p.date, p.deterministic) for p in result.points]
    assert got == expected
    assert all(p.p10 is None and p.p50 is None and p.p90 is None for p in result.points)
    assert result.runway_date is None


def test_same_seed_reproduces_and_different_seed_differs() -> None:
    inputs = ten_invoice_inputs()
    dists = {
        "acme": Distribution((0, 5, 12, 40), 0.05, "party"),
        "beta": Distribution((-3, 2, 30), 0.02, "party"),
        "gamma": Distribution((37,), 0.02, "terms"),
    }
    inputs = ForecastInputs(**{**inputs.__dict__, "distributions": dists})
    a = run(inputs, horizon_days=30, n_paths=200, seed=7)
    b = run(inputs, horizon_days=30, n_paths=200, seed=7)
    c = run(inputs, horizon_days=30, n_paths=200, seed=8)
    assert [(p.p10, p.p50, p.p90) for p in a.points] == [(p.p10, p.p50, p.p90) for p in b.points]
    assert [(p.p10, p.p50, p.p90) for p in a.points] != [(p.p10, p.p50, p.p90) for p in c.points]
    assert all(p.p10 <= p.p50 <= p.p90 for p in a.points)  # type: ignore[operator]
    # deterministic path is unaffected by sampling
    assert [p.deterministic for p in a.points] == [p.deterministic for p in c.points]


def test_bands_are_exact_paise_and_point_mass_collapses_bands() -> None:
    inputs = ten_invoice_inputs()
    zero = {k: Distribution((0,), 0.0, "party") for k in ("acme", "beta", "gamma")}
    inputs = ForecastInputs(
        **{**inputs.__dict__, "distributions": zero, "recurring": (), "expected": ()}
    )
    result = run(inputs, horizon_days=30, n_paths=50, seed=3)
    for p in result.points:
        assert p.p10 == p.p50 == p.p90
        assert p.p10 is not None and p.p10.as_tuple().exponent == -2


def test_runway_is_first_day_p10_below_zero() -> None:
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("1000.00"), AS_OF),
        ap=(APItem(Decimal("1500.00"), AS_OF + timedelta(days=3)),),
    )
    result = run(inputs, horizon_days=10, n_paths=10, seed=1)
    assert result.runway_date == AS_OF + timedelta(days=3)


def test_runway_uses_deterministic_path_when_bands_absent() -> None:
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("100.00"), AS_OF),
        ap=(APItem(Decimal("150.00"), AS_OF + timedelta(days=2)),),
    )
    result = run(inputs, horizon_days=5, n_paths=0, seed=1)
    assert result.runway_date == AS_OF + timedelta(days=2)


def test_overdue_receivable_is_sampled_conditionally_on_still_being_unpaid() -> None:
    # 40 days late already; samples 5 and 10 are impossible, only 60 remains.
    dist = Distribution((5, 10, 60), 0.0, "party")
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        ar=(ARItem("acme", Decimal("100.00"), AS_OF - timedelta(days=40)),),
        distributions={"acme": dist},
    )
    result = run(inputs, horizon_days=30, n_paths=20, seed=1)
    assert result.points[19].p50 == Decimal("100.00")  # day 20 = due + 60
    assert result.points[18].p50 == Decimal("0.00")


def test_overdue_receivable_with_no_feasible_sample_lands_tomorrow() -> None:
    dist = Distribution((5, 10), 0.0, "party")
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        ar=(ARItem("acme", Decimal("100.00"), AS_OF - timedelta(days=40)),),
        distributions={"acme": dist},
    )
    result = run(inputs, horizon_days=5, n_paths=20, seed=1)
    assert result.points[0].p50 == Decimal("100.00")


def test_non_payment_component_removes_receivable_in_some_paths() -> None:
    dist = Distribution((0,), 0.5, "party")
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        ar=(ARItem("acme", Decimal("100.00"), AS_OF + timedelta(days=1)),),
        distributions={"acme": dist},
    )
    result = run(inputs, horizon_days=3, n_paths=400, seed=11)
    assert result.points[-1].p10 == Decimal("0.00")
    assert result.points[-1].p90 == Decimal("100.00")


def test_missing_party_distribution_pays_on_due_date() -> None:
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        ar=(ARItem("unknown", Decimal("100.00"), AS_OF + timedelta(days=2)),),
    )
    result = run(inputs, horizon_days=3, n_paths=5, seed=1)
    assert [p.p50 for p in result.points] == [Decimal("0.00"), Decimal("100.00"), Decimal("100.00")]


def test_expected_invoice_is_bernoulli_and_uses_party_distribution() -> None:
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        expected=(
            Expected(Decimal("100.00"), AS_OF + timedelta(days=1), Decimal("1"), "acme"),
            Expected(Decimal("50.00"), AS_OF - timedelta(days=1), Decimal("0"), None),
        ),
        distributions={"acme": Distribution((2,), 0.0, "party")},
    )
    result = run(inputs, horizon_days=4, n_paths=10, seed=1)
    assert [p.p50 for p in result.points] == [Decimal("0.00")] * 2 + [Decimal("100.00")] * 2
    assert result.points[0].deterministic == Decimal("100.00")  # 100 x 1 on day 1, 50 x 0 on day 1


def test_recurring_jitter_stays_within_window_and_advances_past_as_of() -> None:
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        recurring=(Recurring(Decimal("100.00"), AS_OF - timedelta(days=100), 30),),
    )
    result = run(inputs, horizon_days=60, n_paths=100, seed=5)
    # occurrences advance to the first one after as_of: -100+30*4 = +20, then +50
    assert result.points[59].deterministic == Decimal("-200.00")
    assert result.points[59].p50 == Decimal("-200.00")
    assert result.points[15].deterministic == Decimal("0.00")
    assert result.points[24].p10 == Decimal("-100.00")


def test_fixed_line_cadences_and_stale_once_line() -> None:
    inputs = ForecastInputs(
        opening=OpeningCash(Decimal("0.00"), AS_OF),
        fixed_lines=(
            FixedLine("rent", Decimal("10.00"), date(2026, 8, 31), "monthly", "outflow"),
            FixedLine("gst-audit", Decimal("5.00"), date(2026, 9, 10), "quarterly", "outflow"),
            FixedLine("bonus", Decimal("7.00"), date(2026, 9, 3), "yearly", "inflow"),
            FixedLine("old", Decimal("99.00"), date(2026, 8, 1), "once", "outflow"),
            FixedLine("grant", Decimal("1.00"), date(2026, 9, 2), "once", "inflow"),
        ),
    )
    result = run(inputs, horizon_days=400, n_paths=0, seed=1)
    by_date = {p.date: p.deterministic for p in result.points}
    # grant +1 (2 Sep), bonus +7 (3 Sep), audit -5 (10 Sep); "old" once-line is dropped.
    assert by_date[date(2026, 9, 9)] == Decimal("8.00")
    assert by_date[date(2026, 9, 10)] == Decimal("3.00")
    # monthly from 31 Aug advanced to 30 Sep (day clamp) then 31 Oct (anchor-based stepping)
    assert by_date[date(2026, 9, 29)] == Decimal("3.00")
    assert by_date[date(2026, 9, 30)] == Decimal("-7.00")
    assert by_date[date(2026, 10, 30)] == Decimal("-7.00")
    assert by_date[date(2026, 10, 31)] == Decimal("-17.00")
    assert by_date[date(2026, 12, 10)] == by_date[date(2026, 12, 9)] - Decimal("5.00")
    assert by_date[date(2027, 9, 3)] == by_date[date(2027, 9, 2)] + Decimal("7.00")


def test_add_months_clamps_to_month_end() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_invalid_arguments_are_rejected() -> None:
    inputs = ForecastInputs(opening=OpeningCash(Decimal("0"), AS_OF))
    with pytest.raises(ValueError):
        run(inputs, horizon_days=0, n_paths=0, seed=1)
    with pytest.raises(ValueError):
        run(inputs, horizon_days=5, n_paths=-1, seed=1)
    with pytest.raises(ValueError):
        run(
            ForecastInputs(
                opening=OpeningCash(Decimal("0"), AS_OF),
                recurring=(Recurring(Decimal("1"), AS_OF, 0),),
            ),
            horizon_days=5,
            n_paths=0,
            seed=1,
        )
