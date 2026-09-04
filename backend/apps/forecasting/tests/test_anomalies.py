"""§8.5 expense anomalies, duplicates, revenue concentration."""

from datetime import date
from decimal import Decimal

from apps.forecasting.domain.anomalies import (
    ExpenseRecord,
    RevenueRecord,
    detect_duplicates,
    detect_expense_anomalies,
    revenue_concentration,
    robust_z,
)


def _rec(key: str, d: date, amount: str, party: str = "saas-co", cat: str | None = "saas"):
    return ExpenseRecord(
        key=key, party_key=party, category_key=cat, invoice_date=d, amount=Decimal(amount)
    )


def test_four_x_saas_bill_is_flagged_on_amount() -> None:
    records = [
        _rec("m1", date(2026, 5, 1), "5000"),
        _rec("m2", date(2026, 6, 1), "5000"),
        _rec("m3", date(2026, 7, 1), "5000"),
        _rec("m4", date(2026, 8, 1), "20000"),
    ]
    flags = detect_expense_anomalies(records)
    assert [(a.key, a.kind) for a in flags] == [("m4", "amount")]
    assert flags[0].z is not None and flags[0].z > 3
    assert flags[0].party_key == "saas-co" and flags[0].category_key == "saas"


def test_window_start_limits_flags_but_not_statistics() -> None:
    records = [
        _rec("m1", date(2026, 5, 1), "5000"),
        _rec("m2", date(2026, 6, 1), "20000"),
        _rec("m3", date(2026, 7, 1), "5000"),
        _rec("m4", date(2026, 8, 1), "5000"),
        _rec("m5", date(2026, 9, 1), "5000"),
    ]
    assert [a.key for a in detect_expense_anomalies(records)] == ["m2"]
    assert detect_expense_anomalies(records, window_start=date(2026, 7, 1)) == ()


def test_unusual_gap_is_flagged() -> None:
    dates = [
        date(2026, 1, 1),
        date(2026, 1, 31),
        date(2026, 3, 2),
        date(2026, 4, 1),
        date(2026, 5, 1),
    ]
    records = [_rec(f"g{i}", d, "1000") for i, d in enumerate(dates)]
    records.append(_rec("g5", date(2026, 8, 29), "1000"))  # 120-day gap
    flags = detect_expense_anomalies(records)
    assert [(a.key, a.kind) for a in flags] == [("g5", "gap")]


def test_small_groups_are_not_z_scored() -> None:
    records = [
        _rec("a", date(2026, 1, 1), "100"),
        _rec("b", date(2026, 2, 1), "100"),
        _rec("c", date(2026, 3, 1), "9000"),
    ]
    assert detect_expense_anomalies(records) == ()


def test_new_vendor_over_fifty_thousand_is_flagged() -> None:
    records = [
        _rec("n1", date(2026, 8, 20), "60000.00", party="newco", cat=None),
        _rec("n2", date(2026, 8, 21), "10000.00", party="newco2", cat=None),
    ]
    flags = detect_expense_anomalies(records)
    assert [(a.key, a.kind) for a in flags] == [("n1", "new_vendor")]
    assert flags[0].z is None


def test_established_vendor_large_bill_is_not_new_vendor() -> None:
    records = [_rec(f"e{i}", date(2026, i, 1), "70000") for i in range(1, 6)]
    kinds = {a.kind for a in detect_expense_anomalies(records)}
    assert "new_vendor" not in kinds


def test_duplicate_detection_same_party_amount_within_a_rupee_and_seven_days() -> None:
    records = [
        _rec("d1", date(2026, 8, 1), "1000.00", party="v"),
        _rec("d2", date(2026, 8, 4), "1000.50", party="v"),
        _rec("d3", date(2026, 8, 20), "1000.00", party="v"),  # too far
        _rec("d4", date(2026, 8, 5), "1002.00", party="v"),  # amount off by 2
        _rec("d5", date(2026, 8, 5), "1000.00", party="w"),  # other party
    ]
    dups = detect_duplicates(records)
    assert [(a.key, a.related_key) for a in dups] == [("d2", "d1")]
    assert dups[0].kind == "duplicate"


def test_revenue_concentration_flags_top1_and_top3() -> None:
    c = revenue_concentration(
        [
            RevenueRecord("a", Decimal("50")),
            RevenueRecord("b", Decimal("30")),
            RevenueRecord("c", Decimal("20")),
        ]
    )
    assert c.top1_party == "a" and c.top1_share == Decimal("0.5000")
    assert c.top3_parties == ("a", "b", "c") and c.top3_share == Decimal("1.0000")
    assert c.is_top1_flagged and c.is_top3_flagged


def test_revenue_concentration_spread_is_not_flagged_and_sums_per_party() -> None:
    records = [RevenueRecord(f"p{i % 10}", Decimal("10")) for i in range(20)]
    c = revenue_concentration(records)
    assert c.top1_share == Decimal("0.1000") and c.top3_share == Decimal("0.3000")
    assert not c.is_top1_flagged and not c.is_top3_flagged


def test_revenue_concentration_with_no_revenue() -> None:
    c = revenue_concentration([])
    assert c.top1_party is None and c.top1_share == Decimal("0")
    assert c.top3_parties == () and not c.is_top1_flagged


def test_robust_z_uses_mad_and_floors_scale_when_mad_is_zero() -> None:
    assert robust_z([10, 10, 10, 10]) == [Decimal("0.00")] * 4
    z = robust_z([100, 100, 100, 200])
    assert z[:3] == [Decimal("0.00")] * 3 and z[3] > 3
    z = robust_z([0, 0, 0, 5])
    assert z[3] == Decimal("3.37")  # scale floor of 1 when median is 0
    z = robust_z([1, 2, 3, 4, 100])
    assert z[4] > 3 and abs(z[0]) < 3
