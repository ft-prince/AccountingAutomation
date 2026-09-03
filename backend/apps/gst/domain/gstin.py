"""GSTIN format and checksum validation (PROJECT_SPECS §3.1).

Layout: [2 state][10 PAN][1 entity][Z][1 check]. The check digit is a base-36
weighted sum over the first 14 characters with alternating weights 1,2 starting
with weight 1 on the first character (verified against real GSTINs).
"""

import re
from dataclasses import dataclass
from datetime import date

from apps.gst.domain.state_codes import get_state, is_valid_state

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(BASE36_ALPHABET)
CHECKSUM_INPUT_LENGTH = 14
_CHECKSUM_INPUT_PATTERN = re.compile(r"^[0-9A-Z]{14}$")


@dataclass(frozen=True)
class GSTINValidation:
    is_valid: bool
    state_code: str | None
    pan: str | None
    entity_code: str | None
    errors: list[str]


def validate_format(gstin: str) -> bool:
    """Structural check only. Passing this does not make a GSTIN valid."""
    return GSTIN_PATTERN.match(gstin) is not None


def compute_checksum(first14: str) -> str:
    """Return the base-36 check character for the first 14 characters of a GSTIN."""
    if _CHECKSUM_INPUT_PATTERN.match(first14) is None:
        raise ValueError(
            f"checksum input must be exactly {CHECKSUM_INPUT_LENGTH} chars of 0-9A-Z, "
            f"got {first14!r}"
        )
    total = 0
    for index, char in enumerate(first14):
        weight = 1 if index % 2 == 0 else 2
        product = BASE36_ALPHABET.index(char) * weight
        total += product // BASE + product % BASE
    return BASE36_ALPHABET[(BASE - total % BASE) % BASE]


def validate(gstin: str, on_date: date | None = None) -> GSTINValidation:
    """Full validation: format, state code as of `on_date`, and checksum."""
    if not validate_format(gstin):
        return GSTINValidation(False, None, None, None, ["format: does not match GSTIN pattern"])

    state_code = gstin[:2]
    pan = gstin[2:12]
    entity_code = gstin[12]
    expected_check = compute_checksum(gstin[:14])
    actual_check = gstin[14]

    errors = [
        *_state_errors(state_code, on_date),
        *(
            [f"checksum: expected {expected_check}, got {actual_check}"]
            if actual_check != expected_check
            else []
        ),
    ]
    return GSTINValidation(not errors, state_code, pan, entity_code, errors)


def _state_errors(state_code: str, on_date: date | None) -> list[str]:
    if get_state(state_code) is None:
        return [f"state: {state_code} is not a valid state code"]
    if not is_valid_state(state_code, on_date):
        return [f"state: {state_code} is not valid on this date"]
    return []
