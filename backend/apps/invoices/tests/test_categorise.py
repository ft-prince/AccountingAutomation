"""Rules table for line-level categorisation. Pure: no database."""

from decimal import Decimal

import pytest

from apps.invoices.domain.categorise import (
    CATEGORY_NAMES,
    FALLBACK_CONFIDENCE,
    HSN_CONFIDENCE,
    KEYWORD_CONFIDENCE,
    PARTY_DEFAULT_CONFIDENCE,
    match_hsn,
    match_keyword,
    normalise,
    suggest_category,
)


@pytest.mark.parametrize(
    ("hsn_sac", "description", "expected"),
    [
        # real lines seen on Indian invoices
        ("998315", "Cloud compute Sep-25", "Software & SaaS"),
        ("998314", "Custom app development", "Software & SaaS"),
        ("997331", "Annual software licence", "Software & SaaS"),
        ("996333", "Team lunch", "Meals & Entertainment"),
        ("997212", "Office rent", "Rent"),
        ("996511", "Road freight — Pune to Mumbai", "Freight & Logistics"),
        ("998311", "Management consultancy retainer", "Professional Services"),
        ("998365", "Google Ads media buy", "Marketing"),
        ("9987", "Installation service", "Repairs & Maintenance"),
        ("8543", "Edge sensor module", "Hardware & Equipment"),
        ("8471", "Laptop", "Hardware & Equipment"),
        ("997212 ", "Warehouse rent", "Rent"),
        ("99713", "Group health policy", "Insurance"),
        ("997119", "Payment gateway commission", "Bank Charges"),
        ("998519", "Contract staff — Aug", "Salaries & Contractors"),
        ("999113", "Municipal trade licence fee", "Statutory Fees"),
        ("9984", "Broadband — Sep", "Utilities"),
    ],
)
def test_hsn_rules_pick_the_seeded_category(hsn_sac, description, expected) -> None:  # type: ignore[no-untyped-def]
    got = suggest_category(hsn_sac, description, None)
    assert got.name == expected and got.name in CATEGORY_NAMES
    assert got.confidence == HSN_CONFIDENCE
    assert got.reason.startswith("HSN/SAC")


def test_meals_line_is_the_itc_blocked_category() -> None:
    """996333 outdoor catering → Meals & Entertainment, seeded itc_eligible=False (§3.7)."""
    got = suggest_category("996333", "Team lunch with client", None)
    assert got.name == "Meals & Entertainment"


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Monthly SaaS subscription", "Software & SaaS"),
        ("Facebook advertising", "Marketing"),
        ("Legal opinion on lease", "Professional Services"),
        ("Rent for Sep 2026", "Rent"),
        ("Electricity bill", "Utilities"),
        ("Flight Mumbai-Delhi", "Travel"),
        ("Dinner with auditors", "Meals & Entertainment"),
        ("Office supplies", "Office Supplies"),
        ("Dell monitor", "Hardware & Equipment"),
        ("NEFT bank charges", "Bank Charges"),
        ("Payroll for August", "Salaries & Contractors"),
        ("Fire insurance", "Insurance"),
        ("Courier charges", "Freight & Logistics"),
        ("AMC for lift", "Repairs & Maintenance"),
        ("ROC filing fees", "Statutory Fees"),
    ],
)
def test_keyword_rules_when_the_code_is_missing(description, expected) -> None:  # type: ignore[no-untyped-def]
    got = suggest_category("", description, None)
    assert got.name == expected
    assert got.confidence == KEYWORD_CONFIDENCE
    assert "description mentions" in got.reason


def test_unknown_code_still_falls_through_to_keywords() -> None:
    got = suggest_category("0000", "Annual maintenance contract", None)
    assert got.name == "Repairs & Maintenance" and got.confidence == KEYWORD_CONFIDENCE


def test_nonsense_line_falls_back_to_party_default_then_other() -> None:
    nonsense = "Zzz item 4471"
    with_default = suggest_category("", nonsense, "Marketing")
    assert with_default.name == "Marketing"
    assert with_default.confidence == PARTY_DEFAULT_CONFIDENCE
    assert "party default" in with_default.reason

    without_default = suggest_category("", nonsense, None)
    assert without_default.name == "Other"
    assert without_default.confidence == FALLBACK_CONFIDENCE
    assert without_default.reason == "no rule matched"

    assert suggest_category("", nonsense, "").name == "Other"


def test_code_beats_keyword() -> None:
    """A hardware HSN wins over a 'consulting' word in the description."""
    got = suggest_category("8471", "Laptop bought through our consulting partner", None)
    assert got.name == "Hardware & Equipment"


def test_helpers() -> None:
    assert normalise("Office Supplies!") == "office supplie"
    assert normalise("SaaS") == "saa"
    assert normalise("") == ""
    assert match_hsn("N/A") is None
    assert match_hsn("1234") is None
    assert match_keyword("nothing here") is None
    assert match_keyword("Cloud hosting")[0] == "Software & SaaS"  # type: ignore[index]
    assert isinstance(suggest_category("8471", "x", None).confidence, Decimal)
