"""Generate the downloadable sample files served at /samples and linked from /guide.

Run: cd backend && .venv/bin/python scripts/make_samples.py
Everything is deterministic, so re-running produces byte-identical files.
"""

import csv
import io
import json
import sys
import zipfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from apps.gst.domain.gstin import compute_checksum  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "samples"


def gstin(prefix: str) -> str:
    return prefix + compute_checksum(prefix)


# The demo org's own GSTIN: a vendor bill addressed to it ingests as `inward`.
NEXREN = gstin("27AAGFF2194N1Z")
ACME = gstin("27AAPFU0939F1Z")  # Maharashtra  → intra-state, CGST+SGST
BHARAT = gstin("29AABCT1332L1Z")  # Karnataka    → inter-state, IGST
ROBU = gstin("24AACCR5055K1Z")  # Gujarat      → inter-state, IGST
TATA = gstin("27AAACT2727Q1Z")  # customer for the outward sample


def build_pdf(lines: list[str]) -> bytes:
    """Single-page text-layer PDF. Text layer matters: extraction sends the PDF itself
    rather than page images (PROJECT_SPECS §5)."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    body = "BT /F1 10 Tf 40 800 Td 14 TL " + " ".join(f"({esc(ln)}) Tj T*" for ln in lines) + " ET"
    stream = body.encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def rupees(v: Decimal) -> str:
    return f"{v:,.2f}"


def invoice_lines(
    *,
    supplier: str,
    supplier_addr: str,
    supplier_gstin: str,
    recipient: str,
    recipient_addr: str,
    recipient_gstin: str,
    number: str,
    inv_date: str,
    due: str,
    pos: str,
    item: str,
    hsn: str,
    qty: str,
    unit: Decimal,
    rate: Decimal,
    intra: bool,
    stated_total: Decimal | None = None,
) -> list[str]:
    taxable = (unit * Decimal(qty)).quantize(Decimal("0.01"))
    if intra:
        half = (taxable * rate / 200).quantize(Decimal("0.01"))
        heads = [f"CGST {rate / 2}%: {rupees(half)}", f"SGST {rate / 2}%: {rupees(half)}"]
        tax = half * 2
    else:
        igst = (taxable * rate / 100).quantize(Decimal("0.01"))
        heads = [f"IGST {rate}%: {rupees(igst)}"]
        tax = igst
    total = stated_total if stated_total is not None else taxable + tax
    return [
        "TAX INVOICE",
        supplier,
        supplier_addr,
        f"GSTIN: {supplier_gstin}",
        "",
        f"Invoice No: {number}    Invoice Date: {inv_date}    Due Date: {due}",
        f"Place of Supply: {pos}    Reverse Charge: No",
        "",
        f"Bill To: {recipient}",
        recipient_addr,
        f"GSTIN: {recipient_gstin}" if recipient_gstin else "GSTIN: ",
        "",
        f"1  {item}   HSN/SAC {hsn}   Qty {qty}   Rate {rupees(unit)}   Taxable {rupees(taxable)}",
        "",
        f"Taxable Value: {rupees(taxable)}",
        *heads,
        "Round Off: 0.00",
        f"Invoice Total: {rupees(total)}",
        "",
        "Bank: HDFC Bank   A/c 50200012345678   IFSC HDFC0000123",
        "",
        "For " + supplier,
        "Authorised Signatory",
    ]


SAMPLES: dict[str, list[str]] = {
    # Matches GSTR-2B record 1 exactly.
    "invoice-vendor-intra-18.pdf": invoice_lines(
        supplier="Acme Widgets Pvt Ltd",
        supplier_addr="12 MIDC Road, Pune 411001, Maharashtra",
        supplier_gstin=ACME,
        recipient="Nexren AI Private Limited",
        recipient_addr="4 Tech Park, Andheri East, Mumbai 400093, Maharashtra",
        recipient_gstin=NEXREN,
        number="ACM-2026-0042",
        inv_date="05/08/2026",
        due="04/09/2026",
        pos="27-Maharashtra",
        item="Edge sensor module, industrial grade",
        hsn="8543",
        qty="8",
        unit=Decimal("5000.00"),
        rate=Decimal("18"),
        intra=True,
    ),
    # GSTR-2B carries the same invoice with a different number format -> fuzzy match.
    "invoice-vendor-inter-18.pdf": invoice_lines(
        supplier="Bharat Cloud Services",
        supplier_addr="Hosur Road, Bengaluru 560068, Karnataka",
        supplier_gstin=BHARAT,
        recipient="Nexren AI Private Limited",
        recipient_addr="4 Tech Park, Andheri East, Mumbai 400093, Maharashtra",
        recipient_gstin=NEXREN,
        number="BCS-2026-1189",
        inv_date="12/08/2026",
        due="11/09/2026",
        pos="27-Maharashtra",
        item="Cloud compute, August 2026",
        hsn="998315",
        qty="1",
        unit=Decimal("40000.00"),
        rate=Decimal("18"),
        intra=False,
    ),
    # GSTR-2B reports a higher value -> value_mismatch.
    "invoice-vendor-value-mismatch.pdf": invoice_lines(
        supplier="Robu Electronics",
        supplier_addr="GIDC Estate, Vadodara 390010, Gujarat",
        supplier_gstin=ROBU,
        recipient="Nexren AI Private Limited",
        recipient_addr="4 Tech Park, Andheri East, Mumbai 400093, Maharashtra",
        recipient_gstin=NEXREN,
        number="RBU-2026-0777",
        inv_date="20/08/2026",
        due="19/09/2026",
        pos="27-Maharashtra",
        item="Controller boards, batch of 20",
        hsn="8537",
        qty="20",
        unit=Decimal("1000.00"),
        rate=Decimal("18"),
        intra=False,
    ),
    # Two deliberate defects: no recipient GSTIN (Rule 46) and a total 500 too high (arithmetic).
    "invoice-broken.pdf": invoice_lines(
        supplier="Swiggy Corporate",
        supplier_addr="Koramangala, Bengaluru 560034, Karnataka",
        supplier_gstin=BHARAT,
        recipient="Nexren AI Private Limited",
        recipient_addr="4 Tech Park, Mumbai 400093",
        recipient_gstin="",
        number="SWG/2026/00931",
        inv_date="22/08/2026",
        due="",
        pos="27-Maharashtra",
        item="Team lunch catering",
        hsn="996333",
        qty="1",
        unit=Decimal("10000.00"),
        rate=Decimal("18"),
        intra=False,
        stated_total=Decimal("12300.00"),
    ),
    # We are the supplier here, so this ingests as an outward (sales) invoice.
    "invoice-sales-outward.pdf": invoice_lines(
        supplier="Nexren AI Private Limited",
        supplier_addr="4 Tech Park, Andheri East, Mumbai 400093, Maharashtra",
        supplier_gstin=NEXREN,
        recipient="Tata Steel Digital",
        recipient_addr="Bombay House, Fort, Mumbai 400001, Maharashtra",
        recipient_gstin=TATA,
        number="NX-2627-0501",
        inv_date="25/08/2026",
        due="24/09/2026",
        pos="27-Maharashtra",
        item="Industrial AI platform subscription, August 2026",
        hsn="998314",
        qty="1",
        unit=Decimal("450000.00"),
        rate=Decimal("18"),
        intra=True,
    ),
}


def write_pdfs() -> list[str]:
    written = []
    for name, lines in SAMPLES.items():
        (OUT / name).write_bytes(build_pdf(lines))
        written.append(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in SAMPLES:
            zf.writestr(name, (OUT / name).read_bytes())
    (OUT / "invoices-bulk.zip").write_bytes(buf.getvalue())
    return [*written, "invoices-bulk.zip"]


def write_csv(name: str, header: list[str], rows: list[list[str]]) -> str:
    with (OUT / name).open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return name


def write_statements() -> list[str]:
    """Column names are exactly the per-bank mappings in payments/services/statements.py."""
    hdfc = write_csv(
        "bank-statement-hdfc.csv",
        [
            "Date",
            "Narration",
            "Chq./Ref.No.",
            "Value Dt",
            "Withdrawal Amt.",
            "Deposit Amt.",
            "Closing Balance",
        ],
        [
            [
                "01/09/26",
                "NEFT CR-TATA STEEL DIGITAL-UTR8830012",
                "UTR8830012",
                "01/09/26",
                "",
                "5,31,000.00",
                "12,45,000.00",
            ],
            [
                "02/09/26",
                "UPI-ACME WIDGETS PVT LTD-9920",
                "UPI9920",
                "02/09/26",
                "47,200.00",
                "",
                "11,97,800.00",
            ],
            [
                "03/09/26",
                "NEFT DR-BHARAT CLOUD SERVICES",
                "UTR7741188",
                "03/09/26",
                "47,200.00",
                "",
                "11,50,600.00",
            ],
            ["04/09/26", "BANK CHARGES SEP", "", "04/09/26", "590.00", "", "11,50,010.00"],
        ],
    )
    icici = write_csv(
        "bank-statement-icici.csv",
        [
            "Transaction Date",
            "Transaction Remarks",
            "Cheque Number",
            "Withdrawal Amount (INR )",
            "Deposit Amount (INR )",
            "Balance (INR )",
        ],
        [
            [
                "01/09/2026",
                "NEFT/RELIANCE INDUSTRIAL IOT/ABC001",
                "ABC001",
                "",
                "448400.00",
                "2688800.00",
            ],
            ["02/09/2026", "ACH/PRIME WORKSPACE RENT LLP/AUG", "", "100300.00", "", "2588500.00"],
            ["03/09/2026", "IMPS/ROBU ELECTRONICS/0777", "0777", "23600.00", "", "2564900.00"],
        ],
    )
    sbi = write_csv(
        "bank-statement-sbi.csv",
        [
            "Txn Date",
            "Value Date",
            "Description",
            "Ref No./Cheque No.",
            "Debit",
            "Credit",
            "Balance",
        ],
        [
            [
                "01 Sep 2026",
                "01 Sep 2026",
                "TO TRANSFER-UPI/DR/GOOGLE CLOUD INDIA",
                "",
                "33040.00",
                "",
                "981000.00",
            ],
            [
                "02 Sep 2026",
                "02 Sep 2026",
                "BY TRANSFER-NEFT/CR/MAHINDRA AUTOMATION",
                "NEFT77321",
                "",
                "306800.00",
                "1287800.00",
            ],
            [
                "03 Sep 2026",
                "03 Sep 2026",
                "TO TRANSFER-NEFT/DR/ADANI ELECTRICITY",
                "NEFT77400",
                "21240.00",
                "",
                "1266560.00",
            ],
        ],
    )
    generic = write_csv(
        "bank-statement-generic.csv",
        ["date", "description", "reference", "amount", "balance"],
        [
            [
                "2026-09-01",
                "Payout from Siemens India Partner",
                "SIE-9001",
                "590000.00",
                "1590000.00",
            ],
            ["2026-09-02", "Atlassian India subscription", "ATL-2211", "-11210.00", "1578790.00"],
            ["2026-09-03", "Freelance Devs Collective", "FDC-0099", "-106200.00", "1472590.00"],
        ],
    )
    return [hdfc, icici, sbi, generic]


def write_2b() -> list[str]:
    """GSTN GSTR-2B download shape. Designed against the three vendor PDFs above so that,
    once those are confirmed in books, the run produces one of every match type."""
    payload = {
        "data": {
            "gstin": NEXREN,
            "rtnprd": "082026",
            "docdata": {
                "b2b": [
                    {
                        "ctin": ACME,
                        "trdnm": "Acme Widgets Pvt Ltd",
                        "inv": [
                            {  # identical to the books invoice -> exact
                                "inum": "ACM-2026-0042",
                                "idt": "05-08-2026",
                                "val": 47200.00,
                                "pos": "27",
                                "rev": "N",
                                "itcavl": "Y",
                                "txval": 40000.00,
                                "igst": 0.00,
                                "cgst": 3600.00,
                                "sgst": 3600.00,
                                "cess": 0.00,
                            }
                        ],
                    },
                    {
                        "ctin": BHARAT,
                        "trdnm": "Bharat Cloud Services",
                        "inv": [
                            {  # same invoice, different separators and a day out -> fuzzy
                                "inum": "BCS/2026/1189",
                                "idt": "13-08-2026",
                                "val": 47200.00,
                                "pos": "27",
                                "rev": "N",
                                "itcavl": "Y",
                                "txval": 40000.00,
                                "igst": 7200.00,
                                "cgst": 0.00,
                                "sgst": 0.00,
                                "cess": 0.00,
                            }
                        ],
                    },
                    {
                        "ctin": ROBU,
                        "trdnm": "Robu Electronics",
                        "inv": [
                            {  # supplier reported 500 more than the bill -> value_mismatch
                                "inum": "RBU-2026-0777",
                                "idt": "20-08-2026",
                                "val": 24100.00,
                                "pos": "27",
                                "rev": "N",
                                "itcavl": "Y",
                                "txval": 20423.73,
                                "igst": 3676.27,
                                "cgst": 0.00,
                                "sgst": 0.00,
                                "cess": 0.00,
                            }
                        ],
                    },
                    {
                        "ctin": gstin("06AABCU9603R1Z"),
                        "trdnm": "Unknown Traders",
                        "inv": [
                            {  # never entered in books -> missing_in_books
                                "inum": "UT-2026-5510",
                                "idt": "28-08-2026",
                                "val": 17700.00,
                                "pos": "27",
                                "rev": "N",
                                "itcavl": "Y",
                                "txval": 15000.00,
                                "igst": 2700.00,
                                "cgst": 0.00,
                                "sgst": 0.00,
                                "cess": 0.00,
                            }
                        ],
                    },
                ]
            },
        }
    }
    (OUT / "gstr2b-082026.json").write_text(json.dumps(payload, indent=2) + "\n")
    return ["gstr2b-082026.json"]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    names = write_pdfs() + write_statements() + write_2b()
    print(f"wrote {len(names)} files to {OUT}")
    for n in names:
        print(f"  {n}  {(OUT / n).stat().st_size:,} bytes")
