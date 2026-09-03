"""Financial years, return periods and due dates (PROJECT_SPECS §3.8).

FY = 1 Apr–31 Mar; "2026-27" = 2026-04-01..2027-03-31. Periods are "MMYYYY".
GSTR-1: 11th monthly / 13th of the month after the quarter (QRMP).
GSTR-3B: 20th monthly / 22nd (group 1) or 24th (group 2) after the quarter (QRMP).
ITC deadline: 30 Nov after FY end.
"""

import re
from datetime import date
from typing import Literal

FY_START_MONTH = 4
FY_END_MONTH = 3
FY_END_DAY = 31
MONTHS_PER_QUARTER = 3
MONTHS_PER_YEAR = 12

GSTR1_MONTHLY_DAY = 11
GSTR1_QRMP_DAY = 13
GSTR3B_MONTHLY_DAY = 20
GSTR3B_QRMP_DAY_BY_GROUP: dict[int, int] = {1: 22, 2: 24}
ITC_DEADLINE_MONTH = 11
ITC_DEADLINE_DAY = 30

StateGroup = Literal[1, 2]

_FY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
_PERIOD_PATTERN = re.compile(r"^(0[1-9]|1[0-2])(\d{4})$")


def fy_for_date(d: date) -> str:
    """Financial year label like "2026-27" for the FY containing `d`."""
    start_year = d.year if d.month >= FY_START_MONTH else d.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def fy_bounds(fy: str) -> tuple[date, date]:
    """(first day, last day) of a financial year label; ValueError when malformed."""
    match = _FY_PATTERN.match(fy)
    if match is None:
        raise ValueError(f"malformed financial year {fy!r}; expected YYYY-YY")
    start_year = int(match.group(1))
    if int(match.group(2)) != (start_year + 1) % 100:
        raise ValueError(f"non-consecutive financial year {fy!r}")
    return date(start_year, FY_START_MONTH, 1), date(start_year + 1, FY_END_MONTH, FY_END_DAY)


def return_period(d: date) -> str:
    """Return period label "MMYYYY" for the month containing `d`."""
    return f"{d.month:02d}{d.year:04d}"


def _parse_period(period: str) -> tuple[int, int]:
    match = _PERIOD_PATTERN.match(period)
    if match is None:
        raise ValueError(f"malformed return period {period!r}; expected MMYYYY")
    return int(match.group(1)), int(match.group(2))


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * MONTHS_PER_YEAR + (month - 1) + delta
    return index // MONTHS_PER_YEAR, index % MONTHS_PER_YEAR + 1


def _quarter_end(year: int, month: int) -> tuple[int, int]:
    remaining = (MONTHS_PER_QUARTER - month % MONTHS_PER_QUARTER) % MONTHS_PER_QUARTER
    return _add_months(year, month, remaining)


def _filing_month(period: str, qrmp: bool) -> tuple[int, int]:
    """Year/month in which the return for `period` falls due."""
    month, year = _parse_period(period)
    if qrmp:
        year, month = _quarter_end(year, month)
    return _add_months(year, month, 1)


def due_date_gstr1(period: str, qrmp: bool) -> date:
    year, month = _filing_month(period, qrmp)
    return date(year, month, GSTR1_QRMP_DAY if qrmp else GSTR1_MONTHLY_DAY)


def due_date_gstr3b(period: str, qrmp: bool, state_group: StateGroup) -> date:
    if state_group not in GSTR3B_QRMP_DAY_BY_GROUP:
        raise ValueError(f"unknown state_group {state_group!r}; expected 1 or 2")
    year, month = _filing_month(period, qrmp)
    day = GSTR3B_QRMP_DAY_BY_GROUP[state_group] if qrmp else GSTR3B_MONTHLY_DAY
    return date(year, month, day)


def itc_deadline(fy: str) -> date:
    """Last date to claim ITC for a FY: 30 Nov following the FY end (§3.8)."""
    _, fy_end = fy_bounds(fy)
    return date(fy_end.year, ITC_DEADLINE_MONTH, ITC_DEADLINE_DAY)
