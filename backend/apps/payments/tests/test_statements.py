import io
import re
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
    imports = client_a.get("/api/bank/statements/").json()["results"]
    assert [i["filename"] for i in imports] == ["h.csv"]
    assert client_b.get("/api/bank/statements/").json()["results"] == []
    # a bad mapping key is a 400, not a KeyError
    r = client_a.post(
        "/api/bank/statements/import",
        {"account": str(acct.id), "mapping": "nope", "file": SimpleUploadedFile("h.csv", b"x")},
    )
    assert r.status_code == 400
    assert len(MAPPINGS) == 6


# ---------------------------------------------------------------- real-world export shapes

HDFC_EXPORT = """HDFC BANK Ltd.,,,,,,
Account Statement,,,,,,
Account No :,50200012345678,,,,,
From : 01/08/2026 To : 31/08/2026,,,,,,
,,,,,,
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
************,************,************,************,************,************,************
01/08/26,NEFT CR-ACME WIDGETS-UTR123,UTR123,01/08/26,,"11,800.00","2,50,000.00"
02/08/26,UPI-AWS INDIA-98765,98765,02/08/26,"4,720.00",,"2,45,280.00"
************,************,************,************,************,************,************
,,,,Opening Balance,Dr Count,Cr Count
"""
ICICI_HTML = b"""<html><body><table>
<tr><td>Account Number</td><td>000405001234</td></tr>
<tr><td>Transaction Period</td><td>01/08/2026 to 31/08/2026</td></tr>
<tr><th>S No.</th><th>Value Date</th><th>Transaction Date</th><th>Cheque Number</th>
<th>Transaction Remarks</th><th>Withdrawal Amount (INR )</th><th>Deposit Amount (INR )</th>
<th>Balance (INR )</th></tr>
<tr><td>1</td><td>03/08/2026</td><td>03/08/2026</td><td></td><td>NEFT/ZETA CORP/ABC001</td>
<td>0</td><td>23600.00</td><td>268880.00</td></tr>
<tr><td>2</td><td>04/08/2026</td><td>04/08/2026</td><td>-</td><td>ACH/RENT AUG</td>
<td>50000.00</td><td>0</td><td>218880.00</td></tr>
</table></body></html>"""


def test_hdfc_export_with_preamble_and_separators(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    imp = import_statement(acct, data=HDFC_EXPORT.encode(), filename="Acct.txt", fmt="csv")
    assert imp.mapping == "hdfc" and imp.rows_imported == 2
    assert sorted(
        BankTransaction.objects.filter(bank_account=acct).values_list("amount", flat=True)
    ) == [
        Decimal("-4720.00"),
        Decimal("11800.00"),
    ]


def test_icici_xls_is_really_html(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    imp = import_statement(acct, data=ICICI_HTML, filename="stmt.xls", fmt="xls")
    assert imp.mapping == "icici" and imp.rows_imported == 2


def test_legacy_binary_xls_is_refused(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    with pytest.raises(StatementError, match="Legacy binary .xls"):
        import_statement(acct, data=b"\xd0\xcf\x11\xe0\xa1\xb1", filename="s.xls", fmt="xls")


def test_header_case_and_spacing_tolerant(org_a) -> None:  # type: ignore[no-untyped-def]
    csv = (
        "TRANSACTION DATE;transaction remarks;Withdrawal Amount(INR);"
        "Deposit Amount (INR);Balance(INR)\n"
    )
    csv += "05-Aug-2026;POS/AMAZON;1,000.00 Dr;;9,000.00 Cr\n"
    acct = BankAccountFactory(org=org_a.org)
    imp = import_statement(acct, data=csv.encode(), filename="s.csv", fmt="csv")
    assert imp.mapping == "icici" and imp.rows_imported == 1
    tx = BankTransaction.objects.get(bank_account=acct)
    assert (tx.amount, tx.balance_after) == (Decimal("-1000.00"), Decimal("9000.00"))


def test_password_protected_pdf_gives_clear_error(org_a, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    from pdfplumber.utils.exceptions import PdfminerException

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise PdfminerException(PDFPasswordIncorrect())

    monkeypatch.setattr(pdfplumber, "open", boom)
    acct = BankAccountFactory(org=org_a.org)
    with pytest.raises(StatementError, match="password-protected"):
        import_statement(acct, data=b"%PDF-1.4", filename="s.pdf", fmt="pdf")


def _table_pdf(rows: list[list[str]], xs: list[int]) -> bytes:
    """Unruled statement page: each cell placed at a fixed x like a real bank PDF."""
    from scripts.make_samples import build_pdf

    pdf = build_pdf([])
    body = " ".join(
        f"BT /F1 9 Tf {x} {800 - 14 * i} Td ({cell}) Tj ET"
        for i, row in enumerate(rows)
        for x, cell in zip(xs, row, strict=True)
        if cell
    ).encode()
    head, _, tail = pdf.partition(b"stream\n")
    _, _, tail = tail.partition(b"endstream")
    head = re.sub(rb"/Length \d+", f"/Length {len(body)}".encode(), head)
    return head + b"stream\n" + body + b"\nendstream" + tail


def test_pdf_unruled_table_import(org_a) -> None:  # type: ignore[no-untyped-def]
    rows = [
        ["Txn Date", "Description", "Debit", "Credit", "Balance"],
        ["05 Aug 2026", "TO TRANSFER-UPI/DR/GOOGLE", "3540.00", "", "215340.00"],
        ["06 Aug 2026", "BY TRANSFER-NEFT/CR/BETA", "", "59000.00", "274340.00"],
    ]
    acct = BankAccountFactory(org=org_a.org)
    data = _table_pdf(rows, [40, 110, 300, 380, 460])
    imp = import_statement(acct, data=data, filename="s.pdf", fmt="pdf")
    assert imp.rows_imported == 2 and imp.mapping == "sbi"
    assert BankTransaction.objects.get(bank_account=acct, date="2026-08-06").amount == Decimal(
        "59000.00"
    )


def test_no_data_rows_under_header(org_a) -> None:  # type: ignore[no-untyped-def]
    acct = BankAccountFactory(org=org_a.org)
    csv = "date,description,amount\nOpening Balance,,100\n"
    with pytest.raises(StatementError, match="no transaction rows"):
        import_statement(acct, data=csv.encode(), filename="s.csv", fmt="csv")
