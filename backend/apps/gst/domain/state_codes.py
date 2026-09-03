"""GST state codes (PROJECT_SPECS §3.1). A table, not a dict literal.

01 (J&K) … 38 (Ladakh), plus 97 Other Territory and 99 Other Country.
25 (Daman & Diu) was discontinued when it merged into 26 on 26 Jan 2020:
accepted on historical invoices, rejected on new ones.
"""

from dataclasses import dataclass
from datetime import date

DAMAN_DIU_MERGER_DATE = date(2020, 1, 26)


@dataclass(frozen=True)
class StateCode:
    code: str
    name: str
    is_active: bool


STATE_CODES: tuple[StateCode, ...] = (
    StateCode("01", "Jammu & Kashmir", True),
    StateCode("02", "Himachal Pradesh", True),
    StateCode("03", "Punjab", True),
    StateCode("04", "Chandigarh", True),
    StateCode("05", "Uttarakhand", True),
    StateCode("06", "Haryana", True),
    StateCode("07", "Delhi", True),
    StateCode("08", "Rajasthan", True),
    StateCode("09", "Uttar Pradesh", True),
    StateCode("10", "Bihar", True),
    StateCode("11", "Sikkim", True),
    StateCode("12", "Arunachal Pradesh", True),
    StateCode("13", "Nagaland", True),
    StateCode("14", "Manipur", True),
    StateCode("15", "Mizoram", True),
    StateCode("16", "Tripura", True),
    StateCode("17", "Meghalaya", True),
    StateCode("18", "Assam", True),
    StateCode("19", "West Bengal", True),
    StateCode("20", "Jharkhand", True),
    StateCode("21", "Odisha", True),
    StateCode("22", "Chhattisgarh", True),
    StateCode("23", "Madhya Pradesh", True),
    StateCode("24", "Gujarat", True),
    StateCode("25", "Daman & Diu", False),
    StateCode("26", "Dadra & Nagar Haveli and Daman & Diu", True),
    StateCode("27", "Maharashtra", True),
    StateCode("28", "Andhra Pradesh (Before Division)", True),
    StateCode("29", "Karnataka", True),
    StateCode("30", "Goa", True),
    StateCode("31", "Lakshadweep", True),
    StateCode("32", "Kerala", True),
    StateCode("33", "Tamil Nadu", True),
    StateCode("34", "Puducherry", True),
    StateCode("35", "Andaman & Nicobar Islands", True),
    StateCode("36", "Telangana", True),
    StateCode("37", "Andhra Pradesh", True),
    StateCode("38", "Ladakh", True),
    StateCode("97", "Other Territory", True),
    StateCode("99", "Other Country", True),
)

_BY_CODE: dict[str, StateCode] = {state.code: state for state in STATE_CODES}


def get_state(code: str) -> StateCode | None:
    """Look up a two-digit state code; None when unknown."""
    return _BY_CODE.get(code)


def is_valid_state(code: str, on_date: date | None = None) -> bool:
    """True if the code exists and was in force on `on_date`.

    Inactive codes are valid only for dates strictly before the merger date.
    With no date the check is treated as "new invoice" and inactive codes fail.
    """
    state = get_state(code)
    if state is None:
        return False
    if state.is_active:
        return True
    return on_date is not None and on_date < DAMAN_DIU_MERGER_DATE
