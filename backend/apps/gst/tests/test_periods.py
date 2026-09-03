"""§3.8 returns, deadlines, periods. FY = 1 Apr–31 Mar; all period logic uses FY."""

from datetime import date

import pytest

from apps.gst.domain.periods import (
    due_date_gstr1,
    due_date_gstr3b,
    fy_bounds,
    fy_for_date,
    itc_deadline,
    return_period,
)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 4, 1), "2026-27"),
        (date(2026, 3, 31), "2025-26"),
        (date(2027, 1, 15), "2026-27"),
        (date(2027, 3, 31), "2026-27"),
        (date(2027, 4, 1), "2027-28"),
        (date(2099, 12, 31), "2099-00"),
    ],
)
def test_fy_for_date(day: date, expected: str) -> None:
    assert fy_for_date(day) == expected


def test_fy_bounds_2026_27() -> None:
    assert fy_bounds("2026-27") == (date(2026, 4, 1), date(2027, 3, 31))


def test_fy_bounds_century_rollover() -> None:
    assert fy_bounds("2099-00") == (date(2099, 4, 1), date(2100, 3, 31))


@pytest.mark.parametrize("bad", ["2026-28", "2026/27", "202627", "26-27", "abcd-ef", ""])
def test_fy_bounds_rejects_malformed_or_non_consecutive(bad: str) -> None:
    with pytest.raises(ValueError, match="financial year"):
        fy_bounds(bad)


def test_fy_roundtrip() -> None:
    start, end = fy_bounds("2026-27")
    assert fy_for_date(start) == "2026-27"
    assert fy_for_date(end) == "2026-27"


@pytest.mark.parametrize(
    ("day", "expected"),
    [(date(2026, 4, 15), "042026"), (date(2026, 12, 1), "122026"), (date(2027, 1, 31), "012027")],
)
def test_return_period(day: date, expected: str) -> None:
    assert return_period(day) == expected


@pytest.mark.parametrize(
    ("period", "qrmp", "expected"),
    [
        ("042026", False, date(2026, 5, 11)),
        ("122026", False, date(2027, 1, 11)),
        ("042026", True, date(2026, 7, 13)),  # Apr–Jun quarter
        ("062026", True, date(2026, 7, 13)),
        ("072026", True, date(2026, 10, 13)),
        ("102026", True, date(2027, 1, 13)),  # Oct–Dec quarter, year rollover
        ("032027", True, date(2027, 4, 13)),
    ],
)
def test_due_date_gstr1(period: str, qrmp: bool, expected: date) -> None:
    assert due_date_gstr1(period, qrmp) == expected


@pytest.mark.parametrize(
    ("period", "qrmp", "state_group", "expected"),
    [
        ("042026", False, 1, date(2026, 5, 20)),
        ("042026", False, 2, date(2026, 5, 20)),
        ("122026", False, 1, date(2027, 1, 20)),
        ("042026", True, 1, date(2026, 7, 22)),
        ("042026", True, 2, date(2026, 7, 24)),
        ("032027", True, 2, date(2027, 4, 24)),
    ],
)
def test_due_date_gstr3b(period: str, qrmp: bool, state_group: int, expected: date) -> None:
    assert due_date_gstr3b(period, qrmp, state_group) == expected  # type: ignore[arg-type]


def test_due_date_gstr3b_rejects_unknown_state_group() -> None:
    with pytest.raises(ValueError, match="state_group"):
        due_date_gstr3b("042026", True, 3)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["132026", "002026", "0420", "ab2026", "2026-04", ""])
def test_due_dates_reject_malformed_period(bad: str) -> None:
    with pytest.raises(ValueError, match="MMYYYY"):
        due_date_gstr1(bad, False)
    with pytest.raises(ValueError, match="MMYYYY"):
        due_date_gstr3b(bad, False, 1)


@pytest.mark.parametrize(
    ("fy", "expected"), [("2026-27", date(2027, 11, 30)), ("2024-25", date(2025, 11, 30))]
)
def test_itc_deadline_is_30_nov_after_fy_end(fy: str, expected: date) -> None:
    assert itc_deadline(fy) == expected
