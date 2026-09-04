"""Scenario overrides (PROJECT_SPECS §8.4) applied immutably to ForecastInputs.

Each override is a mapping with a "kind" plus its arguments:
  delay_customer {party, days}   lose_customer {party}   delay_vendor {party, days}
  add_fixed_line {name, amount, cadence, next_date, direction}   remove_fixed_line {name}
  collection_policy_shift {days}  (signed change to days_to_pay; negative = collect sooner)
  new_hire {amount, start}       (monthly outflow from `start`)
Values are validated here because they arrive from JSON; money must be a string or int.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

from apps.forecasting.domain.distributions import shift_distribution
from apps.forecasting.domain.engine import Cadence, Direction, FixedLine, ForecastInputs

Override = Mapping[str, object]
CADENCES: tuple[str, ...] = ("monthly", "quarterly", "yearly", "once")
DIRECTIONS: tuple[str, ...] = ("inflow", "outflow")
NEW_HIRE_LINE_NAME = "new_hire"


class ScenarioError(ValueError):
    pass


def _str(o: Override, key: str) -> str:
    value = o.get(key)
    if not isinstance(value, str) or not value:
        raise ScenarioError(f"'{key}' must be a non-empty string")
    return value


def _int(o: Override, key: str) -> int:
    value = o.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScenarioError(f"'{key}' must be an integer")
    return value


def _decimal(o: Override, key: str) -> Decimal:
    value = o.get(key)
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise ScenarioError(f"'{key}' must be a decimal string or integer, never a float")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ScenarioError(f"'{key}' is not a valid amount") from exc


def _date(o: Override, key: str) -> date:
    value = o.get(key)
    if not isinstance(value, str):
        raise ScenarioError(f"'{key}' must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ScenarioError(f"'{key}' is not an ISO date") from exc


def _choice(o: Override, key: str, allowed: Sequence[str]) -> str:
    value = _str(o, key)
    if value not in allowed:
        raise ScenarioError(f"'{key}' must be one of {', '.join(allowed)}")
    return value


def _delay_customer(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    party, delta = _str(o, "party"), timedelta(days=_int(o, "days"))
    return replace(
        inputs,
        ar=tuple(
            replace(a, due_date=a.due_date + delta) if a.party_key == party else a
            for a in inputs.ar
        ),
        expected=tuple(
            replace(e, expected_date=e.expected_date + delta) if e.party_key == party else e
            for e in inputs.expected
        ),
    )


def _lose_customer(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    party = _str(o, "party")
    return replace(
        inputs,
        ar=tuple(a for a in inputs.ar if a.party_key != party),
        expected=tuple(e for e in inputs.expected if e.party_key != party),
    )


def _delay_vendor(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    party, delta = _str(o, "party"), timedelta(days=_int(o, "days"))
    return replace(
        inputs,
        ap=tuple(
            replace(a, due_date=a.due_date + delta) if a.party_key == party else a
            for a in inputs.ap
        ),
    )


def _add_fixed_line(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    line = FixedLine(
        name=_str(o, "name"),
        amount=_decimal(o, "amount"),
        next_date=_date(o, "next_date"),
        cadence=cast(Cadence, _choice(o, "cadence", CADENCES)),
        direction=cast(Direction, _choice(o, "direction", DIRECTIONS)),
    )
    return replace(inputs, fixed_lines=(*inputs.fixed_lines, line))


def _remove_fixed_line(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    name = _str(o, "name")
    return replace(inputs, fixed_lines=tuple(f for f in inputs.fixed_lines if f.name != name))


def _collection_policy_shift(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    days = _int(o, "days")
    return replace(
        inputs,
        distributions={k: shift_distribution(d, days) for k, d in inputs.distributions.items()},
    )


def _new_hire(inputs: ForecastInputs, o: Override) -> ForecastInputs:
    line = FixedLine(
        NEW_HIRE_LINE_NAME, _decimal(o, "amount"), _date(o, "start"), "monthly", "outflow"
    )
    return replace(inputs, fixed_lines=(*inputs.fixed_lines, line))


_HANDLERS: dict[str, Callable[[ForecastInputs, Override], ForecastInputs]] = {
    "delay_customer": _delay_customer,
    "lose_customer": _lose_customer,
    "delay_vendor": _delay_vendor,
    "add_fixed_line": _add_fixed_line,
    "remove_fixed_line": _remove_fixed_line,
    "collection_policy_shift": _collection_policy_shift,
    "new_hire": _new_hire,
}


def apply_overrides(inputs: ForecastInputs, overrides: Sequence[Override]) -> ForecastInputs:
    result = inputs
    for override in overrides:
        if not isinstance(override, Mapping):
            raise ScenarioError("each override must be an object")
        kind = _str(override, "kind")
        handler = _HANDLERS.get(kind)
        if handler is None:
            raise ScenarioError(f"unknown override kind '{kind}'")
        result = handler(result, override)
    return result
