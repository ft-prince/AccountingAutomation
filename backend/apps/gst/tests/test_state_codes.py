"""§3.1 state code table: 01–38 plus 97/99; 25 discontinued after the 2020 merger."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from apps.gst.domain.state_codes import (
    DAMAN_DIU_MERGER_DATE,
    STATE_CODES,
    StateCode,
    get_state,
    is_valid_state,
)


def test_table_covers_01_to_38_plus_97_and_99_in_order() -> None:
    codes = [state.code for state in STATE_CODES]
    assert codes == [f"{n:02d}" for n in range(1, 39)] + ["97", "99"]


def test_table_is_immutable_tuple_of_frozen_dataclasses() -> None:
    assert isinstance(STATE_CODES, tuple)
    assert all(isinstance(state, StateCode) for state in STATE_CODES)
    with pytest.raises(FrozenInstanceError):
        STATE_CODES[0].name = "changed"  # type: ignore[misc]


def test_daman_and_diu_is_the_only_inactive_state() -> None:
    inactive = [state.code for state in STATE_CODES if not state.is_active]
    assert inactive == ["25"]
    assert get_state("25") == StateCode("25", "Daman & Diu", False)


def test_26_is_merged_union_territory_name() -> None:
    assert get_state("26") == StateCode("26", "Dadra & Nagar Haveli and Daman & Diu", True)


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("01", "Jammu & Kashmir"),
        ("07", "Delhi"),
        ("27", "Maharashtra"),
        ("29", "Karnataka"),
        ("36", "Telangana"),
        ("37", "Andhra Pradesh"),
        ("38", "Ladakh"),
        ("97", "Other Territory"),
        ("99", "Other Country"),
    ],
)
def test_get_state_returns_named_entry(code: str, name: str) -> None:
    state = get_state(code)
    assert state is not None
    assert state.name == name
    assert state.is_active is True


@pytest.mark.parametrize("code", ["00", "39", "50", "98", "1", "027", "", "AB"])
def test_get_state_returns_none_for_unknown_code(code: str) -> None:
    assert get_state(code) is None


def test_merger_date_is_26_jan_2020() -> None:
    assert DAMAN_DIU_MERGER_DATE == date(2020, 1, 26)


@pytest.mark.parametrize(
    ("code", "on_date", "expected"),
    [
        ("27", None, True),
        ("27", date(2026, 9, 4), True),
        ("99", date(2026, 1, 1), True),
        ("25", None, False),
        ("25", date(2019, 12, 31), True),
        ("25", date(2020, 1, 25), True),
        ("25", date(2020, 1, 26), False),
        ("25", date(2026, 1, 15), False),
        ("00", None, False),
        ("39", date(2019, 1, 1), False),
    ],
)
def test_is_valid_state(code: str, on_date: date | None, expected: bool) -> None:
    assert is_valid_state(code, on_date) is expected
