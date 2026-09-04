"""§8.4 scenario overrides applied to engine inputs."""

from datetime import date
from decimal import Decimal

import pytest

from apps.forecasting.domain.distributions import Distribution
from apps.forecasting.domain.engine import (
    APItem,
    ARItem,
    Expected,
    FixedLine,
    ForecastInputs,
    OpeningCash,
)
from apps.forecasting.domain.scenarios import ScenarioError, apply_overrides

AS_OF = date(2026, 9, 1)


def base() -> ForecastInputs:
    return ForecastInputs(
        opening=OpeningCash(Decimal("10"), AS_OF),
        ar=(
            ARItem("acme", Decimal("100"), date(2026, 9, 10)),
            ARItem("beta", Decimal("200"), date(2026, 9, 12)),
        ),
        ap=(
            APItem(Decimal("50"), date(2026, 9, 5), party_key="v1"),
            APItem(Decimal("60"), date(2026, 9, 6), party_key="v2"),
        ),
        fixed_lines=(
            FixedLine("payroll", Decimal("1000"), date(2026, 9, 28), "monthly", "outflow"),
        ),
        expected=(Expected(Decimal("70"), date(2026, 9, 20), Decimal("0.5"), "acme"),),
        distributions={"acme": Distribution((5, 10), 0.02, "party")},
    )


def test_delay_customer_shifts_receivables_and_pipeline_for_that_party() -> None:
    out = apply_overrides(base(), [{"kind": "delay_customer", "party": "acme", "days": 15}])
    assert out.ar[0].due_date == date(2026, 9, 25)
    assert out.ar[1].due_date == date(2026, 9, 12)
    assert out.expected[0].expected_date == date(2026, 10, 5)
    assert base().ar[0].due_date == date(2026, 9, 10)  # input untouched


def test_lose_customer_drops_receivables_and_pipeline() -> None:
    out = apply_overrides(base(), [{"kind": "lose_customer", "party": "acme"}])
    assert [a.party_key for a in out.ar] == ["beta"]
    assert out.expected == ()


def test_delay_vendor_shifts_only_that_vendor() -> None:
    out = apply_overrides(base(), [{"kind": "delay_vendor", "party": "v1", "days": 10}])
    assert out.ap[0].due_date == date(2026, 9, 15)
    assert out.ap[1].due_date == date(2026, 9, 6)


def test_add_and_remove_fixed_line() -> None:
    added = apply_overrides(
        base(),
        [
            {
                "kind": "add_fixed_line",
                "name": "loan",
                "amount": "2500.50",
                "cadence": "monthly",
                "next_date": "2026-09-15",
                "direction": "outflow",
            }
        ],
    )
    assert [f.name for f in added.fixed_lines] == ["payroll", "loan"]
    assert added.fixed_lines[1].amount == Decimal("2500.50")
    removed = apply_overrides(added, [{"kind": "remove_fixed_line", "name": "payroll"}])
    assert [f.name for f in removed.fixed_lines] == ["loan"]


def test_collection_policy_shift_moves_every_distribution() -> None:
    out = apply_overrides(base(), [{"kind": "collection_policy_shift", "days": -7}])
    assert out.distributions["acme"].samples == (-2, 3)


def test_new_hire_adds_a_monthly_outflow() -> None:
    out = apply_overrides(base(), [{"kind": "new_hire", "amount": 80000, "start": "2026-10-01"}])
    line = out.fixed_lines[-1]
    assert line.name == "new_hire"
    assert line.amount == Decimal("80000")
    assert line.cadence == "monthly" and line.direction == "outflow"
    assert line.next_date == date(2026, 10, 1)


def test_overrides_apply_in_sequence() -> None:
    out = apply_overrides(
        base(),
        [
            {"kind": "delay_customer", "party": "acme", "days": 1},
            {"kind": "delay_customer", "party": "acme", "days": 2},
        ],
    )
    assert out.ar[0].due_date == date(2026, 9, 13)


@pytest.mark.parametrize(
    "override",
    [
        {"kind": "teleport"},
        {"party": "acme", "days": 3},
        {"kind": "delay_customer", "party": "acme"},
        {"kind": "delay_customer", "party": "acme", "days": "3"},
        {"kind": "delay_customer", "party": "acme", "days": True},
        {"kind": "delay_customer", "party": 7, "days": 3},
        {"kind": "new_hire", "amount": 1.5, "start": "2026-10-01"},
        {"kind": "new_hire", "amount": "abc", "start": "2026-10-01"},
        {"kind": "new_hire", "amount": "10", "start": "next tuesday"},
        {"kind": "new_hire", "amount": "10", "start": 20261001},
        {
            "kind": "add_fixed_line",
            "name": "x",
            "amount": "1",
            "cadence": "weekly",
            "next_date": "2026-09-15",
            "direction": "outflow",
        },
        {
            "kind": "add_fixed_line",
            "name": "x",
            "amount": "1",
            "cadence": "monthly",
            "next_date": "2026-09-15",
            "direction": "sideways",
        },
        "not-a-mapping",
    ],
)
def test_invalid_overrides_raise_scenario_error(override: object) -> None:
    with pytest.raises(ScenarioError):
        apply_overrides(base(), [override])  # type: ignore[list-item]
