"""§8.5 customer payment-delay risk bands."""

from decimal import Decimal

from apps.forecasting.domain.risk import CustomerHistory, score_customer, score_customers


def test_prompt_payer_is_low_risk() -> None:
    h = CustomerHistory(
        party_key="prompt",
        days_to_pay=(-3, -1, 0, 2, -2, 1, 0),
        open_balance=Decimal("20000"),
        overdue_balance=Decimal("0"),
        credit_limit=Decimal("100000"),
    )
    s = score_customer(h)
    assert s.band == "low"
    assert s.score < Decimal("0.35")
    assert s.drivers == ()
    assert s.utilisation == Decimal("0.20")


def test_chronically_late_payer_is_high_risk_with_drivers() -> None:
    h = CustomerHistory(
        party_key="late",
        days_to_pay=(20, 35, 30, 60, 55, 70, 80),
        open_balance=Decimal("130000"),
        overdue_balance=Decimal("104000"),
        credit_limit=Decimal("100000"),
    )
    s = score_customer(h)
    assert s.band == "high"
    assert s.score > Decimal("0.65")
    assert "avg 50.0 days late" in s.drivers
    assert "erratic timing (sd 20.5 days)" in s.drivers
    assert "slowing: +26.7 days over last 6" in s.drivers
    assert "80% of open balance overdue" in s.drivers
    assert "130% of credit limit used" in s.drivers


def test_watch_band_in_the_middle() -> None:
    h = CustomerHistory(
        party_key="mid",
        days_to_pay=(10, 30, 20),
        open_balance=Decimal("1000"),
        overdue_balance=Decimal("300"),
        credit_limit=None,
    )
    s = score_customer(h)
    assert s.band == "watch"
    assert s.utilisation is None
    assert s.trend_days == Decimal("0.0")  # fewer than 4 samples: no trend


def test_no_history_is_reported_as_a_driver() -> None:
    h = CustomerHistory("new", (), Decimal("0"), Decimal("0"), Decimal("0"))
    s = score_customer(h)
    assert s.drivers == ("no payment history",)
    assert s.mean_days == Decimal("0.0")
    assert s.share_overdue == Decimal("0.00")
    assert s.utilisation is None


def test_customers_are_sorted_highest_risk_first() -> None:
    a = CustomerHistory("a", (0, 0, 0), Decimal("0"), Decimal("0"), None)
    b = CustomerHistory("b", (90, 90, 90), Decimal("0"), Decimal("0"), None)
    assert [s.party_key for s in score_customers([a, b])] == ["b", "a"]
