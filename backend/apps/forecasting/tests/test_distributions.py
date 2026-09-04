"""§8.2 fallbacks and §8.3 long-tail non-payment component."""

from apps.forecasting.domain.distributions import (
    FALLBACK_GRACE_DAYS,
    NON_PAYMENT_FLOOR,
    Distribution,
    PaymentRecord,
    build_distribution,
    build_distributions,
    non_payment_share,
    shift_distribution,
)


def _rec(party: str, *days: int, is_paid: bool = True) -> list[PaymentRecord]:
    return [PaymentRecord(party_key=party, days_to_pay=d, is_paid=is_paid) for d in days]


def test_party_with_three_paid_invoices_gets_own_distribution() -> None:
    records = _rec("acme", 2, 5, 9) + _rec("other", 30, 40, 50)
    dist = build_distribution("acme", records, terms_days=30)
    assert dist.source == "party"
    assert dist.samples == (2, 5, 9)
    assert dist.non_payment_probability == NON_PAYMENT_FLOOR


def test_party_with_too_few_samples_falls_back_to_org_wide() -> None:
    records = _rec("acme", 2) + _rec("other", 30, 40, 50)
    dist = build_distribution("acme", records, terms_days=30)
    assert dist.source == "org"
    assert dist.samples == (2, 30, 40, 50)


def test_no_history_at_all_falls_back_to_terms_plus_seven() -> None:
    dist = build_distribution("acme", [], terms_days=45)
    assert dist.source == "terms"
    assert dist.samples == (45 + FALLBACK_GRACE_DAYS,)
    assert dist.non_payment_probability == NON_PAYMENT_FLOOR


def test_thin_org_history_also_falls_back_to_terms() -> None:
    dist = build_distribution("acme", _rec("other", 3, 4), terms_days=30)
    assert dist.source == "terms"


def test_non_payment_share_counts_paid_and_open_invoices_over_120_days_late() -> None:
    records = _rec("acme", 10, 20, 130) + _rec("acme", 150, is_paid=False)
    dist = build_distribution("acme", records, terms_days=30)
    assert dist.samples == (10, 20, 130)
    assert dist.non_payment_probability == 0.5


def test_non_payment_share_is_floored_at_two_percent() -> None:
    dist = build_distribution("acme", _rec("acme", 1, 2, 3, 4), terms_days=30)
    assert dist.non_payment_probability == 0.02


def test_org_fallback_uses_org_wide_non_payment_share() -> None:
    records = _rec("other", 10, 10, 200, 200)
    dist = build_distribution("acme", records, terms_days=30)
    assert dist.source == "org"
    assert dist.non_payment_probability == 0.5


def test_build_distributions_covers_every_known_party() -> None:
    records = _rec("acme", 1, 2, 3) + _rec("beta", 7)
    out = build_distributions(records, terms_by_party={"acme": 30, "beta": 15, "gamma": 60})
    assert set(out) == {"acme", "beta", "gamma"}
    assert out["acme"].source == "party"
    assert out["beta"].source == "org"
    assert out["gamma"].source == "org"


def test_build_distributions_defaults_terms_for_parties_only_seen_in_records() -> None:
    out = build_distributions(_rec("acme", 5), terms_by_party={})
    assert out["acme"].source == "terms"
    assert out["acme"].samples == (30 + FALLBACK_GRACE_DAYS,)


def test_shift_distribution_moves_every_sample() -> None:
    dist = Distribution(samples=(5, 10), non_payment_probability=0.02, source="party")
    shifted = shift_distribution(dist, -7)
    assert shifted.samples == (-2, 3)
    assert shifted.source == "party"
    assert dist.samples == (5, 10)


def test_non_payment_share_of_nothing_is_the_floor() -> None:
    assert non_payment_share([]) == NON_PAYMENT_FLOOR
