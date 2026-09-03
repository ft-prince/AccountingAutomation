"""Seeded set: ≥ 80% auto-match with ZERO false positives."""

from datetime import date
from decimal import Decimal

import pytest

from apps.invoices.factories import InvoiceFactory
from apps.parties.factories import PartyFactory
from apps.payments.factories import BankAccountFactory, TransactionFactory
from apps.payments.models import BankTransaction, MatchStatus
from apps.payments.services import matching

pytestmark = pytest.mark.django_db
D = Decimal


def _inv(org, party, total, direction="outward", number=None, due=None, notes=""):  # type: ignore[no-untyped-def]
    return InvoiceFactory(
        org=org,
        party=party,
        direction=direction,
        status="confirmed",
        total=D(total),
        taxable_value=D(total),
        cgst=0,
        sgst=0,
        invoice_number=number or f"N{total}",
        due_date=due or date(2026, 8, 1),
        notes=notes,
    )


def _txn(acct, amount, desc, ref="", d=date(2026, 8, 3)):  # type: ignore[no-untyped-def]
    return TransactionFactory(
        bank_account=acct, amount=D(amount), description=desc, reference=ref, date=d
    )


@pytest.fixture
def seeded(org_a):  # type: ignore[no-untyped-def]
    org = org_a.org
    acct = BankAccountFactory(org=org)
    acme = PartyFactory(org=org, legal_name="Acme Widgets Pvt Ltd")
    zeta = PartyFactory(org=org, legal_name="Zeta Corp")
    beta = PartyFactory(org=org, legal_name="Beta LLP")
    aws = PartyFactory(org=org, legal_name="Amazon Web Services India")
    expect: dict[str, list] = {}
    # 1 exact amount + name
    i1 = _inv(org, acme, "11800.00", number="A1")
    expect["t1"] = [i1]
    _txn(acct, "11800.00", "NEFT CR ACME WIDGETS", "UTR1").__setattr__("_k", "t1")
    # 2 within ₹1 + name
    i2 = _inv(org, zeta, "23600.00", number="Z1")
    expect["t2"] = [i2]
    _txn(acct, "23599.50", "IMPS ZETA CORP").__setattr__("_k", "t2")
    # 3 sum of two invoices of one party + name
    i3a, i3b = _inv(org, beta, "10000.00", number="B1"), _inv(org, beta, "5000.00", number="B2")
    expect["t3"] = [i3a, i3b]
    _txn(acct, "15000.00", "NEFT BETA LLP CONSOLIDATED").__setattr__("_k", "t3")
    # 4 UTR in notes, description opaque
    i4 = _inv(org, acme, "7777.00", number="A2", notes="expected via UTR9988")
    expect["t4"] = [i4]
    _txn(acct, "7777.00", "NEFT CR 0000", "UTR9988").__setattr__("_k", "t4")
    # 5 debit → inward vendor invoice, name match
    i5 = _inv(org, aws, "4720.00", direction="inward", number="AWS1")
    expect["t5"] = [i5]
    _txn(acct, "-4720.00", "UPI AMAZON WEB SERVICES").__setattr__("_k", "t5")
    # 6 ambiguous: two different parties, same amount, no name → must NOT auto-match
    _inv(org, acme, "5555.00", number="A3")
    _inv(org, zeta, "5555.00", number="Z2")
    expect["t6"] = []
    _txn(acct, "5555.00", "NEFT CR").__setattr__("_k", "t6")
    # 7 credit that equals an INWARD invoice → must not match (wrong direction)
    _inv(org, aws, "9999.00", direction="inward", number="AWS2")
    expect["t7"] = []
    _txn(acct, "9999.00", "NEFT CR AMAZON").__setattr__("_k", "t7")
    # 8 exact amount, name, but far outside date window → still fine (date is only +0.1)
    i8 = _inv(org, zeta, "1234.00", number="Z3", due=date(2026, 3, 1))
    expect["t8"] = [i8]
    _txn(acct, "1234.00", "ZETA CORP", d=date(2026, 8, 20)).__setattr__("_k", "t8")
    # 9 exact amount only, no name, single candidate → 0.6 → propose, not auto
    _inv(org, beta, "3210.00", number="B3")
    expect["t9"] = []
    _txn(acct, "3210.00", "CASH DEP", d=date(2026, 12, 1)).__setattr__("_k", "t9")
    # 10 exact + name + date window
    i10 = _inv(org, acme, "20000.00", number="A4", due=date(2026, 8, 5))
    expect["t10"] = [i10]
    _txn(acct, "20000.00", "ACME WIDGETS PVT LTD PAYMENT").__setattr__("_k", "t10")
    return acct, expect


def test_auto_match_hits_80_percent_with_zero_false_positives(seeded, org_a) -> None:  # type: ignore[no-untyped-def]
    acct, expect = seeded
    result = matching.auto_match(acct.pk, actor=org_a.user)
    matched = BankTransaction.objects.filter(bank_account=acct, match_status=MatchStatus.AUTO)
    matchable = sum(1 for v in expect.values() if v)
    assert result["matched"] == matched.count()
    assert matched.count() / matchable >= 0.8, f"{matched.count()}/{matchable}"
    # zero false positives: every auto-matched txn settled exactly its expected invoices
    for t in matched.select_related("matched_payment"):
        got = sorted(str(a.invoice_id) for a in t.matched_payment.allocations.all())
        key = next(
            k
            for k, v in expect.items()
            if v and sum(i.total for i in v) in (abs(t.amount), abs(t.amount) + D("0.50"))
        )
        assert got == sorted(str(i.pk) for i in expect[key]), key
    # the three traps stayed unmatched
    for amt in ("5555.00", "9999.00", "3210.00"):
        assert (
            BankTransaction.objects.get(bank_account=acct, amount=D(amt)).match_status
            == MatchStatus.UNMATCHED
        )


def test_manual_match_ignore_and_candidates_api(client_a, org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    party = PartyFactory(org=org_a.org, legal_name="Gamma Industries")
    inv = _inv(org_a.org, party, "3210.00", number="G1")
    txn = _txn(acct, "3210.00", "CASH DEP")
    c = client_a.get(f"/api/bank/transactions/{txn.id}/candidates/").json()
    assert c[0]["invoices"][0]["invoice_number"] == "G1" and D(c[0]["score"]) < D("0.80")
    r = client_a.post(
        f"/api/bank/transactions/{txn.id}/match/", {"invoices": [str(inv.id)]}, format="json"
    )
    assert r.status_code == 200 and r.json()["match_status"] == "manual"
    inv.refresh_from_db()
    assert inv.payment_status == "paid"
    other = _txn(acct, "-10.00", "BANK CHARGES")
    assert (
        client_a.post(f"/api/bank/transactions/{other.id}/ignore/").json()["match_status"]
        == "ignored"
    )
    from apps.core.audit import AuditEvent

    assert AuditEvent.objects.filter(action="bank.match.manual").exists()
    assert AuditEvent.objects.filter(action="bank.ignore").exists()


def test_debit_never_matches_outward(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    party = PartyFactory(org=org_a.org, legal_name="Delta")
    inv = _inv(org_a.org, party, "100.00")
    txn = _txn(acct, "-100.00", "DELTA")
    assert matching.candidates_for(txn) == []
    with pytest.raises(ValueError, match="cannot settle"):
        matching.apply_match(txn, [inv], actor=None, status="manual")
