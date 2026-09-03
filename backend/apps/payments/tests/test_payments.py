from datetime import date
from decimal import Decimal

import pytest

from apps.invoices.factories import InvoiceFactory
from apps.invoices.models import Invoice
from apps.invoices.signals import DerivedFieldError
from apps.payments.factories import BankAccountFactory, PaymentFactory
from apps.payments.services.allocation import (
    AllocationError,
    allocate,
    derive_status,
    recompute_invoice,
    refresh_overdue,
)

pytestmark = pytest.mark.django_db
D = Decimal


def _inv(org, total="11800.00", **kw):  # type: ignore[no-untyped-def]
    kw.setdefault("direction", "outward")
    kw.setdefault("status", "confirmed")
    return InvoiceFactory(
        org=org, total=D(total), taxable_value=D("10000"), cgst=D("900"), sgst=D("900"), **kw
    )


def test_derive_status_table() -> None:
    today = date(2026, 9, 1)
    assert derive_status(D("100"), D("0"), date(2026, 9, 10), today) == "unpaid"
    assert derive_status(D("100"), D("40"), date(2026, 9, 10), today) == "partial"
    assert derive_status(D("100"), D("100"), date(2026, 8, 1), today) == "paid"
    assert derive_status(D("100"), D("0"), date(2026, 8, 31), today) == "overdue"
    assert derive_status(D("100"), D("40"), date(2026, 8, 31), today) == "overdue"
    assert derive_status(D("100"), D("0"), None, today) == "unpaid"


def test_transitions_unpaid_partial_paid(org_a) -> None:  # type: ignore[no-untyped-def]
    inv = _inv(org_a.org, due_date=date(2099, 1, 1))
    assert inv.payment_status == "unpaid"
    p1 = PaymentFactory(org=org_a.org, party=inv.party, amount=D("5000"))
    allocate(p1, [(inv, D("5000"))], actor=org_a.user)
    inv.refresh_from_db()
    assert (inv.amount_paid, inv.payment_status) == (D("5000.00"), "partial")
    p2 = PaymentFactory(org=org_a.org, party=inv.party, amount=D("6800"))
    allocate(p2, [(inv, D("6800"))], actor=org_a.user)
    inv.refresh_from_db()
    assert (inv.amount_paid, inv.payment_status) == (D("11800.00"), "paid")


def test_over_allocation_rejected_and_atomic(org_a) -> None:  # type: ignore[no-untyped-def]
    a, b = _inv(org_a.org), _inv(org_a.org)
    b.party = a.party
    b.save()
    p = PaymentFactory(org=org_a.org, party=a.party, amount=D("15000"))
    with pytest.raises(AllocationError, match="exceed the payment"):
        allocate(p, [(a, D("11800")), (b, D("4000"))], actor=org_a.user)
    assert p.allocations.count() == 0
    a.refresh_from_db()
    assert a.amount_paid == 0 and a.payment_status == "unpaid"
    with pytest.raises(AllocationError, match="exceeds outstanding"):
        allocate(p, [(a, D("12000"))], actor=org_a.user)


def test_direction_and_status_guards(org_a) -> None:  # type: ignore[no-untyped-def]
    inward = _inv(org_a.org, direction="inward")
    p = PaymentFactory(org=org_a.org, party=inward.party, amount=D("11800"), direction="received")
    with pytest.raises(AllocationError, match="cannot settle"):
        allocate(p, [(inward, D("100"))], actor=org_a.user)
    pending = _inv(org_a.org, status="needs_review")
    with pytest.raises(AllocationError, match="not confirmed"):
        allocate(
            PaymentFactory(org=org_a.org, amount=D("1")), [(pending, D("1"))], actor=org_a.user
        )


def test_direct_set_of_derived_fields_is_rejected(org_a) -> None:  # type: ignore[no-untyped-def]
    inv = _inv(org_a.org)
    inv.amount_paid = D("500")
    with pytest.raises(DerivedFieldError):
        inv.save()
    inv.refresh_from_db()
    inv.payment_status = "paid"
    with pytest.raises(DerivedFieldError):
        inv.save(update_fields=["payment_status"])
    inv.refresh_from_db()
    inv.notes = "harmless"
    inv.save()  # unrelated edits still work
    assert Invoice.objects.get(pk=inv.pk).amount_paid == 0


def test_overdue_nightly_refresh(org_a) -> None:  # type: ignore[no-untyped-def]
    inv = _inv(org_a.org, due_date=date(2020, 1, 1))
    assert inv.payment_status == "unpaid"
    assert refresh_overdue(org_a.org.pk) == 1
    inv.refresh_from_db()
    assert inv.payment_status == "overdue"
    assert refresh_overdue(org_a.org.pk) == 0
    recompute_invoice(inv, today=date(2019, 1, 1))
    inv.refresh_from_db()
    assert inv.payment_status == "unpaid"


def test_payment_api_create_and_allocate(client_a, org_a, viewer_client) -> None:  # type: ignore[no-untyped-def]
    inv = _inv(org_a.org)
    r = client_a.post(
        "/api/payments/",
        {
            "party": str(inv.party_id),
            "direction": "received",
            "amount": "11800.00",
            "date": "2026-08-01",
            "method": "upi",
            "reference": "UTR123",
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    pid = r.json()["id"]
    assert (
        viewer_client.post(
            f"/api/payments/{pid}/allocate/",
            {"items": [{"invoice": str(inv.id), "amount": "1"}]},
            format="json",
        ).status_code
        == 403
    )
    r = client_a.post(
        f"/api/payments/{pid}/allocate/",
        {"items": [{"invoice": str(inv.id), "amount": "11800.00"}]},
        format="json",
    )
    assert r.status_code == 200, r.json()
    assert r.json()["allocated"] == "11800.00"
    assert client_a.get(f"/api/invoices/{inv.id}/").json()["payment_status"] == "paid"
    r = client_a.post(
        f"/api/payments/{pid}/allocate/",
        {"items": [{"invoice": str(inv.id), "amount": "20000"}]},
        format="json",
    )
    assert r.status_code == 400


def test_balance_snapshot_endpoint(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    r = client_a.post(
        "/api/bank/balance-snapshots/",
        {"bank_account": str(acct.id), "date": "2026-09-01", "balance": "250000.00"},
        format="json",
    )
    assert r.status_code == 201 and r.json()["source"] == "manual"
