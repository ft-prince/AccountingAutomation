"""§8.2 recurring-expense pattern detection."""

from datetime import date, timedelta
from decimal import Decimal

from apps.forecasting.domain.recurring import ExpenseInvoice, detect_patterns, median_decimal


def _inv(key: str, d: date, amount: str, party: str | None = "landlord", cat: str | None = "rent"):  # type: ignore[no-untyped-def]
    return ExpenseInvoice(
        key=key, party_key=party, category_key=cat, invoice_date=d, amount=Decimal(amount)
    )


RENT = [
    _inv("r1", date(2026, 3, 1), "25000.00"),
    _inv("r2", date(2026, 4, 1), "25000.00"),
    _inv("r3", date(2026, 5, 2), "25500.00"),
    _inv("r4", date(2026, 6, 1), "24800.00"),
]


def test_monthly_rent_is_detected_and_one_off_is_ignored() -> None:
    one_off = _inv("x1", date(2026, 4, 20), "80000.00", party="agency", cat="marketing")
    patterns = detect_patterns(RENT + [one_off])
    assert len(patterns) == 1
    p = patterns[0]
    assert p.party_key == "landlord"
    assert p.category_key == "rent"
    assert p.occurrences == 4
    assert p.invoice_keys == ("r1", "r2", "r3", "r4")
    assert p.amount_p50 == Decimal("25000.00")
    assert p.confidence == Decimal("0.67")


def test_period_is_median_of_in_band_gaps() -> None:
    p = detect_patterns(RENT)[0]
    assert p.period_days == 31
    assert p.next_expected == date(2026, 7, 2)


def test_two_occurrences_are_not_a_pattern() -> None:
    assert detect_patterns(RENT[:2]) == ()


def test_irregular_gaps_are_not_a_pattern() -> None:
    irregular = [
        _inv("a", date(2026, 1, 1), "1000"),
        _inv("b", date(2026, 1, 20), "1000"),
        _inv("c", date(2026, 3, 15), "1000"),
        _inv("d", date(2026, 3, 30), "1000"),
    ]
    assert detect_patterns(irregular) == ()


def test_amount_outlier_is_excluded_from_the_cluster() -> None:
    deposit = _inv("dep", date(2026, 4, 15), "75000.00")
    patterns = detect_patterns(RENT + [deposit])
    assert len(patterns) == 1
    assert "dep" not in patterns[0].invoice_keys


def test_quarterly_and_yearly_bands() -> None:
    quarterly = [
        _inv("q1", date(2025, 1, 10), "9000", party="auditor", cat="prof"),
        _inv("q2", date(2025, 4, 10), "9000", party="auditor", cat="prof"),
        _inv("q3", date(2025, 7, 10), "9100", party="auditor", cat="prof"),
    ]
    yearly = [
        _inv("y1", date(2024, 6, 1), "50000", party="insurer", cat="ins"),
        _inv("y2", date(2025, 6, 1), "52000", party="insurer", cat="ins"),
        _inv("y3", date(2026, 6, 1), "54000", party="insurer", cat="ins"),
    ]
    patterns = {p.party_key: p for p in detect_patterns(quarterly + yearly)}
    assert patterns["auditor"].period_days == 91
    assert patterns["auditor"].confidence == Decimal("0.50")
    assert patterns["insurer"].period_days == 365
    assert patterns["insurer"].amount_p50 == Decimal("52000.00")


def test_category_grouping_catches_patterns_without_a_party() -> None:
    saas = [
        _inv("s1", date(2026, 1, 5), "4999", party=None, cat="saas"),
        _inv("s2", date(2026, 2, 5), "4999", party=None, cat="saas"),
        _inv("s3", date(2026, 3, 5), "4999", party=None, cat="saas"),
    ]
    patterns = detect_patterns(saas)
    assert len(patterns) == 1
    assert patterns[0].party_key is None
    assert patterns[0].category_key == "saas"


def test_invoices_consumed_by_a_party_pattern_are_not_reused_by_category() -> None:
    patterns = detect_patterns(RENT)
    assert len(patterns) == 1


def test_non_periodic_cluster_is_dropped_and_search_continues() -> None:
    noise = [
        _inv("n1", date(2026, 1, 3), "100"),
        _inv("n2", date(2026, 1, 9), "100"),
        _inv("n3", date(2026, 2, 27), "100"),
        _inv("n4", date(2026, 3, 2), "100"),
    ]
    periodic = [
        _inv("p1", date(2026, 1, 1), "500"),
        _inv("p2", date(2026, 1, 31), "500"),
        _inv("p3", date(2026, 3, 2), "500"),
    ]
    patterns = detect_patterns(noise + periodic)
    assert [p.invoice_keys for p in patterns] == [("p1", "p2", "p3")]


def test_longest_run_wins_and_break_in_periodicity_ends_the_run() -> None:
    dates = [
        date(2026, 1, 1),
        date(2026, 1, 31),
        date(2026, 3, 2),
        date(2026, 6, 10),
        date(2026, 7, 10),
    ]
    invs = [_inv(f"k{i}", d, "700") for i, d in enumerate(dates)]
    patterns = detect_patterns(invs)
    assert len(patterns) == 1
    assert patterns[0].invoice_keys == ("k0", "k1", "k2")


def test_invoices_without_party_or_category_are_ignored() -> None:
    orphan = [_inv(f"o{i}", date(2026, i, 1), "10", party=None, cat=None) for i in (1, 2, 3)]
    assert detect_patterns(orphan) == ()


def test_median_decimal_even_and_odd() -> None:
    assert median_decimal([Decimal("1"), Decimal("4"), Decimal("2")]) == Decimal("2.00")
    assert median_decimal([Decimal("1"), Decimal("2")]) == Decimal("1.50")


def test_bimodal_amounts_terminate_and_still_find_the_periodic_cluster() -> None:
    # 3 x 100 and 3 x 200 from one party: the median (150) is within 15% of nothing,
    # which must not loop forever (it did on the demo org's ad hoc vendors).
    invoices = [
        _inv(f"lo{i}", date(2026, 1, 5) + timedelta(days=30 * i), "100", party="v", cat=None)
        for i in range(3)
    ] + [
        _inv(f"hi{i}", date(2026, 1, 20) + timedelta(days=30 * i), "200", party="v", cat=None)
        for i in range(3)
    ]
    patterns = detect_patterns(invoices)
    assert sorted((p.amount_p50, p.occurrences) for p in patterns) == [
        (Decimal("100.00"), 3),
        (Decimal("200.00"), 3),
    ]
