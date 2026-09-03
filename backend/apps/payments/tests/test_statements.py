import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.payments.factories import BankAccountFactory
from apps.payments.models import BankBalanceSnapshot, BankTransaction
from apps.payments.services.statements import MAPPINGS, StatementError, import_statement

pytestmark = pytest.mark.django_db

HDFC = """Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/08/26,NEFT CR-ACME WIDGETS-UTR123,UTR123,01/08/26,,"11,800.00","2,50,000.00"
02/08/26,UPI-AWS INDIA-98765,98765,02/08/26,"4,720.00",,"2,45,280.00"
"""
ICICI = (
    "Transaction Date,Transaction Remarks,Cheque Number,"
    "Withdrawal Amount (INR ),Deposit Amount (INR ),Balance (INR )\n"
    """03/08/2026,NEFT/ZETA CORP/ABC001,ABC001,,23600.00,268880.00
04/08/2026,ACH/RENT AUG,,50000.00,,218880.00
"""
)
SBI = """Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance
05 Aug 2026,05 Aug 2026,TO TRANSFER-UPI/DR/GOOGLE CLOUD,,3540.00,,215340.00
06 Aug 2026,06 Aug 2026,BY TRANSFER-NEFT/CR/BETA LLP,NEFT77,,59000.00,274340.00
"""


@pytest.mark.parametrize(
    "csv,key,amounts",
    [
        (HDFC, "hdfc", [Decimal("11800.00"), Decimal("-4720.00")]),
        (ICICI, "icici", [Decimal("23600.00"), Decimal("-50000.00")]),
        (SBI, "sbi", [Decimal("-3540.00"), Decimal("59000.00")]),
    ],
)
def test_three_bank_formats_parse(org_a, csv, key, amounts) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    imp = import_statement(acct, data=csv.encode(), filename="s.csv", fmt="csv")
    assert imp.mapping == key and imp.rows_imported == 2
    got = list(
        BankTransaction.objects.filter(bank_account=acct)
        .order_by("date")
        .values_list("amount", flat=True)
    )
    assert got == amounts
    assert (
        BankTransaction.objects.filter(bank_account=acct, balance_after__isnull=True).count() == 0
    )
    snap = BankBalanceSnapshot.objects.get(bank_account=acct, source="statement")
    assert (
        snap.balance
        == BankTransaction.objects.filter(bank_account=acct).order_by("-date").first().balance_after
    )


def test_reimport_dedupes(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    import_statement(acct, data=HDFC.encode(), filename="a.csv", fmt="csv")
    imp = import_statement(acct, data=HDFC.encode(), filename="a.csv", fmt="csv")
    assert (imp.rows_imported, imp.rows_duplicate) == (0, 2)
    assert BankTransaction.objects.filter(bank_account=acct).count() == 2


def test_xlsx_generic_mapping(org_a) -> None:  # type: ignore[no-untyped-def]
    wb = Workbook()
    ws = wb.active
    ws.append(["date", "description", "reference", "amount", "balance"])
    ws.append(["2026-08-10", "Payout", "R1", 1500.5, 1000])
    ws.append(["2026-08-11", "Fee", "", -20, 980])
    buf = io.BytesIO()
    wb.save(buf)
    acct = BankAccountFactory(org=org_a.org)
    imp = import_statement(acct, data=buf.getvalue(), filename="g.xlsx", fmt="xlsx")
    assert imp.mapping == "generic" and imp.rows_imported == 2
    assert BankTransaction.objects.get(bank_account=acct, reference="R1").amount == Decimal(
        "1500.5"
    )


def test_unknown_columns_rejected(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    with pytest.raises(StatementError, match="No bank mapping"):
        import_statement(acct, data=b"foo,bar\n1,2\n", filename="x.csv", fmt="csv")


def test_import_endpoint_and_org_scope(client_a, client_b, org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    r = client_a.post(
        "/api/bank/statements/import",
        {"account": str(acct.id), "file": SimpleUploadedFile("h.csv", HDFC.encode())},
    )
    assert r.status_code == 201, r.json()
    assert r.json()["rows_imported"] == 2
    assert client_a.get("/api/bank/transactions/?status=unmatched").json()["results"].__len__() == 2
    assert client_b.get("/api/bank/transactions/").json()["results"] == []
    assert len(MAPPINGS) == 4
