"""§3.2 heads, §3.3 rate slabs as data, §3.9 arithmetic with Decimal ROUND_HALF_UP."""

from datetime import date
from decimal import Decimal

import pytest

from apps.gst.domain.supply import SupplyType
from apps.gst.domain.tax import (
    DEFAULT_RATE_TABLE,
    InvoiceTotals,
    LineTax,
    TaxHeads,
    TaxRate,
    compute_invoice_totals,
    compute_line,
    rate_valid_on,
    split_tax,
)

D = Decimal


# --- split_tax -------------------------------------------------------------


def test_intra_18_percent_on_10000_splits_900_900_0() -> None:
    assert split_tax(D("10000"), D("18"), SupplyType.INTRA) == TaxHeads(
        cgst=D("900.00"), sgst=D("900.00"), igst=D("0.00")
    )


def test_inter_18_percent_on_10000_is_igst_1800() -> None:
    assert split_tax(D("10000"), D("18"), SupplyType.INTER) == TaxHeads(
        cgst=D("0.00"), sgst=D("0.00"), igst=D("1800.00")
    )


def test_intra_5_percent_on_1234_56_rounds_each_head_independently() -> None:
    # §3.9 gives tax = round(taxable*rate/100, 2) = round(61.728, 2) = 61.73, but that
    # cannot be split into two equal 2dp heads. We define CGST = round(taxable*rate/200, 2)
    # and SGST identically, so each head is 30.86 (30.864 -> 30.86) and the line carries
    # 61.72 of tax. Heads are never unequal; the 1-paisa difference is absorbed by round_off.
    heads = split_tax(D("1234.56"), D("5"), SupplyType.INTRA)
    assert heads == TaxHeads(cgst=D("30.86"), sgst=D("30.86"), igst=D("0.00"))
    assert heads.cgst == heads.sgst


@pytest.mark.parametrize("supply_type", [SupplyType.EXPORT, SupplyType.SEZ, SupplyType.IMPORT])
def test_export_sez_import_are_igst(supply_type: SupplyType) -> None:
    heads = split_tax(D("1000"), D("18"), supply_type)
    assert heads == TaxHeads(cgst=D("0.00"), sgst=D("0.00"), igst=D("180.00"))


def test_split_uses_round_half_up_not_bankers() -> None:
    # 0.5 * 5 / 100 = 0.025 -> HALF_UP gives 0.03 (HALF_EVEN would give 0.02)
    assert split_tax(D("0.5"), D("5"), SupplyType.INTER).igst == D("0.03")


def test_zero_rate_gives_zero_heads() -> None:
    assert split_tax(D("999.99"), D("0"), SupplyType.INTRA) == TaxHeads(
        cgst=D("0.00"), sgst=D("0.00"), igst=D("0.00")
    )


# --- compute_line ----------------------------------------------------------


def test_compute_line_applies_discount_before_tax() -> None:
    line = compute_line(
        unit_price=D("100"),
        quantity=D("3"),
        discount=D("50"),
        rate=D("18"),
        cess_rate=D("0"),
        supply_type=SupplyType.INTRA,
    )
    assert line == LineTax(
        taxable=D("250.00"),
        cgst=D("22.50"),
        sgst=D("22.50"),
        igst=D("0.00"),
        cess=D("0.00"),
        line_total=D("295.00"),
    )


def test_compute_line_40_percent_with_cess_inter_state() -> None:
    line = compute_line(
        unit_price=D("500"),
        quantity=D("2"),
        discount=D("0"),
        rate=D("40"),
        cess_rate=D("10"),
        supply_type=SupplyType.INTER,
    )
    assert line == LineTax(
        taxable=D("1000.00"),
        cgst=D("0.00"),
        sgst=D("0.00"),
        igst=D("400.00"),
        cess=D("100.00"),
        line_total=D("1500.00"),
    )


def test_compute_line_40_percent_intra_splits_200_200() -> None:
    line = compute_line(D("1000"), D("1"), D("0"), D("40"), D("0"), SupplyType.INTRA)
    assert (line.cgst, line.sgst, line.igst) == (D("200.00"), D("200.00"), D("0.00"))


def test_compute_line_fractional_quantity_rounds_taxable_to_paise() -> None:
    line = compute_line(D("33.333"), D("1.5"), D("0"), D("0"), D("0"), SupplyType.INTRA)
    assert line.taxable == D("50.00")  # 49.9995 -> 50.00 HALF_UP


# --- compute_invoice_totals ------------------------------------------------


def test_three_line_invoice_round_off_minus_30_paise() -> None:
    lines = [
        compute_line(D("100"), D("1"), D("0"), D("18"), D("0"), SupplyType.INTRA),  # 118.00
        compute_line(D("50.25"), D("1"), D("0"), D("5"), D("0"), SupplyType.INTRA),  # 52.77
        compute_line(D("10.53"), D("1"), D("0"), D("0"), D("0"), SupplyType.INTRA),  # 10.53
    ]
    totals = compute_invoice_totals(lines)
    assert totals == InvoiceTotals(
        taxable=D("160.78"),
        cgst=D("10.26"),
        sgst=D("10.26"),
        igst=D("0.00"),
        cess=D("0.00"),
        round_off=D("-0.30"),
        total=D("181"),
    )
    assert totals.taxable + totals.cgst + totals.sgst + totals.igst + totals.cess == D("181.30")


def test_round_off_positive_when_rounding_up() -> None:
    lines = [compute_line(D("100.51"), D("1"), D("0"), D("0"), D("0"), SupplyType.INTRA)]
    totals = compute_invoice_totals(lines)
    assert totals.total == D("101")
    assert totals.round_off == D("0.49")


def test_round_off_exact_half_rounds_up_per_section_170() -> None:
    # Spec §3.9 states the range as -0.50..+0.49; CLAUDE.md mandates ROUND_HALF_UP and
    # CGST Act s.170 rounds 50 paise UP, so the realised range is -0.49..+0.50.
    lines = [compute_line(D("100.50"), D("1"), D("0"), D("0"), D("0"), SupplyType.INTRA)]
    totals = compute_invoice_totals(lines)
    assert totals.total == D("101")
    assert totals.round_off == D("0.50")


def test_round_off_is_zero_for_whole_rupee_invoice() -> None:
    lines = [compute_line(D("10000"), D("1"), D("0"), D("18"), D("0"), SupplyType.INTER)]
    totals = compute_invoice_totals(lines)
    assert totals.igst == D("1800.00")
    assert totals.round_off == D("0.00")
    assert totals.total == D("11800")


def test_empty_invoice_totals_are_zero() -> None:
    assert compute_invoice_totals([]) == InvoiceTotals(
        taxable=D("0.00"),
        cgst=D("0.00"),
        sgst=D("0.00"),
        igst=D("0.00"),
        cess=D("0.00"),
        round_off=D("0.00"),
        total=D("0"),
    )


def test_totals_do_not_mutate_input_lines() -> None:
    lines = [compute_line(D("1"), D("1"), D("0"), D("18"), D("0"), SupplyType.INTRA)]
    snapshot = list(lines)
    compute_invoice_totals(lines)
    assert lines == snapshot


# --- rate table ------------------------------------------------------------


def test_tax_rate_is_frozen_with_effective_range() -> None:
    entry = TaxRate(
        hsn_prefix=None,
        rate=D("18"),
        cess_rate=D("0"),
        effective_from=date(2017, 7, 1),
        effective_to=None,
    )
    assert entry.is_composition is False
    with pytest.raises(AttributeError):
        entry.rate = D("5")  # type: ignore[misc]


def test_default_table_is_tuple_of_tax_rates() -> None:
    assert isinstance(DEFAULT_RATE_TABLE, tuple)
    assert all(isinstance(entry, TaxRate) for entry in DEFAULT_RATE_TABLE)


@pytest.mark.parametrize(
    ("rate", "on_date", "expected"),
    [
        (D("12"), date(2024, 6, 1), True),
        (D("12"), date(2025, 9, 21), True),
        (D("12"), date(2025, 9, 22), False),
        (D("12"), date(2026, 6, 1), False),
        (D("28"), date(2024, 6, 1), True),
        (D("28"), date(2026, 6, 1), False),
        (D("40"), date(2024, 6, 1), False),
        (D("40"), date(2025, 9, 22), True),
        (D("0"), date(2024, 6, 1), True),
        (D("0"), date(2026, 6, 1), True),
        (D("5"), date(2026, 6, 1), True),
        (D("18"), date(2018, 1, 1), True),
        (D("18"), date(2026, 6, 1), True),
        (D("3"), date(2018, 1, 1), True),
        (D("3"), date(2026, 6, 1), True),
        (D("0.25"), date(2026, 6, 1), True),
        (D("18"), date(2017, 6, 30), False),  # before GST
        (D("7"), date(2026, 6, 1), False),  # never a slab
        (D("1.5"), date(2026, 6, 1), False),  # no 1.5% anywhere
    ],
)
def test_general_slabs_valid_as_of_date(rate: Decimal, on_date: date, expected: bool) -> None:
    assert rate_valid_on(rate, on_date, DEFAULT_RATE_TABLE) is expected


def test_rate_equality_ignores_decimal_exponent() -> None:
    assert rate_valid_on(D("18.00"), date(2026, 6, 1), DEFAULT_RATE_TABLE) is True


def test_general_slab_applies_to_any_hsn() -> None:
    assert rate_valid_on(D("18"), date(2026, 6, 1), DEFAULT_RATE_TABLE, hsn_prefix="8471") is True


def test_tobacco_28_plus_comp_cess_valid_until_31_jan_2026() -> None:
    assert rate_valid_on(D("28"), date(2025, 11, 1), DEFAULT_RATE_TABLE, hsn_prefix="2402") is True
    assert rate_valid_on(D("28"), date(2026, 1, 31), DEFAULT_RATE_TABLE, hsn_prefix="2402") is True
    historical = [
        entry for entry in DEFAULT_RATE_TABLE if entry.hsn_prefix == "24" and entry.rate == D("28")
    ]
    assert len(historical) == 1
    assert historical[0].cess_rate > 0
    assert historical[0].effective_to == date(2026, 1, 31)


def test_tobacco_from_1_feb_2026_is_40_with_no_comp_cess() -> None:
    assert rate_valid_on(D("28"), date(2026, 3, 1), DEFAULT_RATE_TABLE, hsn_prefix="2402") is False
    assert rate_valid_on(D("40"), date(2026, 3, 1), DEFAULT_RATE_TABLE, hsn_prefix="2402") is True
    current = [
        entry for entry in DEFAULT_RATE_TABLE if entry.hsn_prefix == "24" and entry.rate == D("40")
    ]
    assert len(current) == 1
    assert current[0].cess_rate == D("0")
    assert current[0].effective_from == date(2026, 2, 1)
    assert current[0].effective_to is None


def test_tobacco_28_is_not_valid_for_non_tobacco_hsn_after_gst_2() -> None:
    assert rate_valid_on(D("28"), date(2025, 11, 1), DEFAULT_RATE_TABLE, hsn_prefix="8471") is False
    assert rate_valid_on(D("28"), date(2025, 11, 1), DEFAULT_RATE_TABLE) is False


def test_bidis_are_18_percent_under_gst_2() -> None:
    assert rate_valid_on(D("18"), date(2026, 3, 1), DEFAULT_RATE_TABLE, hsn_prefix="24031921")


@pytest.mark.parametrize(
    ("rate", "expected"),
    [(D("1"), True), (D("5"), True), (D("6"), True), (D("1.5"), False), (D("18"), False)],
)
def test_composition_rates(rate: Decimal, expected: bool) -> None:
    assert (
        rate_valid_on(rate, date(2026, 6, 1), DEFAULT_RATE_TABLE, is_composition=True) is expected
    )


def test_composition_rates_are_not_regular_slabs() -> None:
    assert rate_valid_on(D("1"), date(2026, 6, 1), DEFAULT_RATE_TABLE) is False
    assert rate_valid_on(D("6"), date(2026, 6, 1), DEFAULT_RATE_TABLE) is False


def test_rate_valid_on_accepts_custom_table() -> None:
    table = (
        TaxRate(
            hsn_prefix=None,
            rate=D("7"),
            cess_rate=D("0"),
            effective_from=date(2030, 1, 1),
            effective_to=date(2030, 12, 31),
        ),
    )
    assert rate_valid_on(D("7"), date(2030, 6, 1), table) is True
    assert rate_valid_on(D("7"), date(2031, 1, 1), table) is False
    assert rate_valid_on(D("7"), date(2029, 12, 31), table) is False
