"""Bank narration → party: the manual match teaches, the next statement matches."""

from datetime import date
from decimal import Decimal

import pytest

from apps.invoices.factories import InvoiceFactory
from apps.parties.factories import PartyFactory
from apps.payments.factories import BankAccountFactory, TransactionFactory
from apps.payments.models import MatchStatus
from apps.payments.services import matching

pytestmark = pytest.mark.django_db
D = Decimal


def _inv(org, party, total, direction="outward", number="X1"):  # type: ignore[no-untyped-def]
    return InvoiceFactory(
        org=org,
        party=party,
        direction=direction,
        status="confirmed",
        total=D(total),
        taxable_value=D(total),
        cgst=0,
        sgst=0,
        invoice_number=number,
        due_date=date(2026, 8, 1),
    )


def _txn(acct, amount, desc, ref="", d=date(2026, 8, 3)):  # type: ignore[no-untyped-def]
    return TransactionFactory(
        bank_account=acct, amount=D(amount), description=desc, reference=ref, date=d
    )


def test_signature_strips_refs_verbs_and_case() -> None:
    assert matching.narration_signature("NEFT CR ACME WIDGETS UTR552211") == "acme widget"
    assert matching.narration_signature("NEFT/CR/ACME WIDGETS/UTR889900") == "acme widget"
    assert matching.narration_signature("BY TRANSFER-UPI/9988776/ZENCO   LABS") == "zenco lab"
    assert matching.narration_signature("IMPS 123456") == ""


def test_manual_match_records_the_alias_and_never_duplicates(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    party = PartyFactory(org=org_a.org, legal_name="Zenco Labs Pvt Ltd")
    inv = _inv(org_a.org, party, "5000.00", number="Z1")
    txn = _txn(acct, "5000.00", "BY TRANSFER-UPI/9988776/ZENCO LABS")
    matching.apply_match(txn, [inv], actor=org_a.user, status=MatchStatus.MANUAL)
    party.refresh_from_db()
    assert party.narration_aliases == ["zenco lab"]

    inv2 = _inv(org_a.org, party, "6000.00", number="Z2")
    txn2 = _txn(acct, "6000.00", "BY TRANSFER-UPI/1122334/ZENCO LABS")
    matching.apply_match(txn2, [inv2], actor=org_a.user, status=MatchStatus.MANUAL)
    party.refresh_from_db()
    assert party.narration_aliases == ["zenco lab"]  # same signature, stored once


def test_auto_match_disabled_for_auto_status(org_a) -> None:  # type: ignore[no-untyped-def]
    """Only a human's decision teaches the alias list."""
    acct = BankAccountFactory(org=org_a.org)
    party = PartyFactory(org=org_a.org, legal_name="Zenco Labs Pvt Ltd")
    inv = _inv(org_a.org, party, "5000.00", number="Z1")
    txn = _txn(acct, "5000.00", "BY TRANSFER-UPI/9988776/ZENCO LABS")
    matching.apply_match(txn, [inv], actor=org_a.user, status=MatchStatus.AUTO)
    party.refresh_from_db()
    assert party.narration_aliases == []


def test_alias_cap_keeps_the_twenty_most_recent(org_a) -> None:  # type: ignore[no-untyped-def]
    party = PartyFactory(org=org_a.org, narration_aliases=[f"alias {i}" for i in range(20)])
    assert matching.learn_alias(party, "ZENCO LABS") == "zenco lab"
    party.refresh_from_db()
    assert len(party.narration_aliases) == 20
    assert party.narration_aliases[-1] == "zenco lab" and "alias 0" not in party.narration_aliases
    assert matching.learn_alias(party, "NEFT CR 4455") is None  # nothing identifying left


def test_learned_alias_auto_matches_the_next_statement(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    party = PartyFactory(org=org_a.org, legal_name="Zenco Labs Pvt Ltd")
    first = _inv(org_a.org, party, "5000.00", number="Z1")
    teach = _txn(acct, "5000.00", "BY TRANSFER-UPI/9988776/ZNCLBS")
    matching.apply_match(teach, [first], actor=org_a.user, status=MatchStatus.MANUAL)
    party.refresh_from_db()
    assert party.narration_aliases == ["znclb"]  # opaque: no name token would ever match

    later = _inv(org_a.org, party, "8000.00", number="Z2")
    txn = _txn(acct, "8000.00", "BY TRANSFER-UPI/5544332/ZNCLBS")
    cands = matching.candidates_for(txn)
    # exact amount 0.50 + alias 0.45 + due-date window 0.10, capped at 1
    assert cands[0].score == D("1") and "learned alias" in cands[0].reasons[1]
    assert matching.should_auto_accept(cands) is not None
    result = matching.auto_match(acct.pk, actor=org_a.user)
    txn.refresh_from_db()
    assert result["matched"] == 1 and txn.match_status == MatchStatus.AUTO
    assert list(txn.matched_payment.allocations.values_list("invoice_id", flat=True)) == [later.pk]


def test_alias_never_crosses_orgs(org_a, org_b) -> None:  # type: ignore[no-untyped-def]
    a_party = PartyFactory(org=org_a.org, legal_name="Zenco Labs Pvt Ltd")
    acct_a = BankAccountFactory(org=org_a.org)
    inv_a = _inv(org_a.org, a_party, "5000.00", number="Z1")
    matching.apply_match(
        _txn(acct_a, "5000.00", "BY TRANSFER-UPI/9988776/ZNCLBS"),
        [inv_a],
        actor=org_a.user,
        status=MatchStatus.MANUAL,
    )
    # Org B has its own party with the same opaque narration and the same amount.
    b_party = PartyFactory(org=org_b.org, legal_name="Other Co")
    acct_b = BankAccountFactory(org=org_b.org)
    _inv(org_b.org, b_party, "8000.00", number="B1")
    b_txn = _txn(acct_b, "8000.00", "BY TRANSFER-UPI/5544332/ZNCLBS")
    cands = matching.candidates_for(b_txn)
    assert [c.invoices[0].org_id for c in cands] == [org_b.org.pk]
    assert cands[0].score < matching.AUTO_ACCEPT_SCORE  # nothing learned in this org yet
    assert matching.should_auto_accept(cands) is None
