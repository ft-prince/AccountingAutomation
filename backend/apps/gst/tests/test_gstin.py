"""§3.1 GSTIN: regex + base-36 checksum + state validity. Regex alone is not validation."""

import json
from datetime import date
from pathlib import Path

import pytest

from apps.gst.domain.gstin import GSTINValidation, compute_checksum, validate, validate_format

FIXTURE = Path(__file__).parent / "fixtures" / "gstins.json"


def _load_fixture() -> dict[str, list[dict[str, str | None]]]:
    with FIXTURE.open() as handle:
        data: dict[str, list[dict[str, str | None]]] = json.load(handle)
    return data


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


FIXTURE_DATA = _load_fixture()
VALID_CASES = FIXTURE_DATA["valid"]
INVALID_CASES = FIXTURE_DATA["invalid"]


def test_fixture_has_50_valid_and_50_invalid() -> None:
    assert len(VALID_CASES) == 50
    assert len(INVALID_CASES) == 50
    reasons = {case["reason"] for case in INVALID_CASES}
    assert reasons == {
        "wrong_length",
        "bad_state",
        "bad_pan",
        "no_z",
        "bad_checksum",
        "inactive_state_25",
    }


@pytest.mark.parametrize(
    ("gstin", "expected"),
    [
        ("27AAPFU0939F1ZV", True),
        ("07AAGFF2194N1Z1", True),
        ("27AAPFU0939F1Z", False),  # 14 chars
        ("27AAPFU0939F1ZVV", False),  # 16 chars
        ("27aapfu0939f1zv", False),  # lowercase
        ("2AAAPFU0939F1ZV", False),  # state not two digits
        ("27AAPF10939F1ZV", False),  # PAN letters block broken
        ("27AAPFU093AF1ZV", False),  # PAN digits block broken
        ("27AAPFU09391F1ZV", False),
        ("27AAPFU0939F0ZV", False),  # entity code 0 not allowed
        ("27AAPFU0939F1YV", False),  # 14th char must be Z
        ("27AAPFU0939F1Z-", False),  # checksum charset
        ("", False),
    ],
)
def test_validate_format(gstin: str, expected: bool) -> None:
    assert validate_format(gstin) is expected


@pytest.mark.parametrize(
    ("first14", "expected"),
    [
        # Real GSTINs: weight 1 on odd (1-indexed) positions, weight 2 on even positions.
        ("27AAPFU0939F1Z", "V"),
        ("07AAGFF2194N1Z", "1"),
        # All zeros: sum 0 -> (36 - 0) % 36 = 0 -> "0"
        ("00000000000000", "0"),
    ],
)
def test_compute_checksum(first14: str, expected: str) -> None:
    assert compute_checksum(first14) == expected


def test_compute_checksum_matches_every_valid_fixture_entry() -> None:
    for case in VALID_CASES:
        gstin = case["gstin"]
        assert gstin is not None
        assert compute_checksum(gstin[:14]) == gstin[14], gstin


@pytest.mark.parametrize(
    "bad", ["27AAPFU0939F1", "27AAPFU0939F1ZV", "27AAPFU0939F1z", "27AAPFU0939F-Z"]
)
def test_compute_checksum_rejects_wrong_length_or_charset(bad: str) -> None:
    with pytest.raises(ValueError, match="14"):
        compute_checksum(bad)


def test_validate_returns_parts_for_valid_gstin() -> None:
    result = validate("27AAPFU0939F1ZV")
    assert result == GSTINValidation(
        is_valid=True,
        state_code="27",
        pan="AAPFU0939F",
        entity_code="1",
        errors=[],
    )


def test_validate_bad_format_gives_no_parts_and_format_error() -> None:
    result = validate("27AAPFU0939F1YV")
    assert result.is_valid is False
    assert result.state_code is None
    assert result.pan is None
    assert result.entity_code is None
    assert result.errors == ["format: does not match GSTIN pattern"]


def test_validate_valid_regex_but_bad_checksum() -> None:
    # 27AAPFU0939F1ZV is real; swap the check digit to K.
    result = validate("27AAPFU0939F1ZK")
    assert result.is_valid is False
    assert result.state_code == "27"
    assert result.pan == "AAPFU0939F"
    assert result.errors == ["checksum: expected V, got K"]


def test_validate_unknown_state_code() -> None:
    first14 = "39AAPFU0939F1Z"
    result = validate(first14 + compute_checksum(first14))
    assert result.is_valid is False
    assert result.errors == ["state: 39 is not a valid state code"]


def test_validate_inactive_state_25_rejected_without_date_and_on_new_dates() -> None:
    first14 = "25AAPFU0939F1Z"
    gstin = first14 + compute_checksum(first14)
    assert validate(gstin).errors == ["state: 25 is not valid on this date"]
    assert validate(gstin, on_date=date(2026, 1, 15)).is_valid is False


def test_validate_inactive_state_25_accepted_on_historical_invoice() -> None:
    first14 = "25AAPFU0939F1Z"
    gstin = first14 + compute_checksum(first14)
    assert validate(gstin, on_date=date(2019, 6, 30)).is_valid is True


def test_validate_collects_state_and_checksum_errors_together() -> None:
    result = validate("39AAPFU0939F1ZK")
    assert result.is_valid is False
    assert len(result.errors) == 2


@pytest.mark.parametrize("case", VALID_CASES, ids=lambda c: str(c["gstin"]))
def test_fixture_valid_gstins_validate(case: dict[str, str | None]) -> None:
    gstin = case["gstin"]
    assert gstin is not None
    result = validate(gstin, on_date=_parse_date(case["on_date"]))
    assert result.is_valid is True, result.errors
    assert result.state_code == gstin[:2]


@pytest.mark.parametrize("case", INVALID_CASES, ids=lambda c: f"{c['reason']}-{c['gstin']}")
def test_fixture_invalid_gstins_are_rejected(case: dict[str, str | None]) -> None:
    gstin = case["gstin"]
    assert gstin is not None
    result = validate(gstin, on_date=_parse_date(case["on_date"]))
    assert result.is_valid is False
    assert result.errors
