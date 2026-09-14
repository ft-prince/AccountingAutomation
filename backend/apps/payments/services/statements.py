"""Bank statement import: per-bank column mappings, sha256 per row, signed amounts."""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction

from apps.payments.models import (
    BankAccount,
    BankBalanceSnapshot,
    BankStatementImport,
    BankTransaction,
)
from apps.payments.services.statement_readers import (
    StatementError,
    find_header,
    grid_to_rows,
    normalise_header,
    read_grid,
)

__all__ = ["MAPPINGS", "StatementError", "import_statement", "parse_rows", "read_rows"]


@dataclass(frozen=True)
class ColumnMapping:
    key: str
    date: str
    description: str
    debit: str | None
    credit: str | None
    amount: str | None  # single signed column
    reference: str | None
    balance: str | None
    date_formats: tuple[str, ...]


# Column headers as they appear in the bank's own export (matched after normalise_header).
# Registry, not if-statements.
DATE_FORMATS = (
    "%d/%m/%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %B %Y",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
)
MAPPINGS: dict[str, ColumnMapping] = {
    "hdfc": ColumnMapping(
        "hdfc",
        "Date",
        "Narration",
        "Withdrawal Amt.",
        "Deposit Amt.",
        None,
        "Chq./Ref.No.",
        "Closing Balance",
        DATE_FORMATS,
    ),
    "icici": ColumnMapping(
        "icici",
        "Transaction Date",
        "Transaction Remarks",
        "Withdrawal Amount (INR )",
        "Deposit Amount (INR )",
        None,
        "Cheque Number",
        "Balance (INR )",
        DATE_FORMATS,
    ),
    "sbi": ColumnMapping(
        "sbi",
        "Txn Date",
        "Description",
        "Debit",
        "Credit",
        None,
        "Ref No./Cheque No.",
        "Balance",
        DATE_FORMATS,
    ),
    "axis": ColumnMapping(
        "axis",
        "Tran Date",
        "Particulars",
        "Debit",
        "Credit",
        None,
        "Chq No",
        "Balance",
        DATE_FORMATS,
    ),
    "kotak": ColumnMapping(
        "kotak",
        "Transaction Date",
        "Description",
        "Debit",
        "Credit",
        None,
        "Chq / Ref number",
        "Balance",
        DATE_FORMATS,
    ),
    "generic": ColumnMapping(
        "generic",
        "date",
        "description",
        "debit",
        "credit",
        "amount",
        "reference",
        "balance",
        DATE_FORMATS,
    ),
}
DATE_ONLY = re.compile(r"^\s*(\d{1,2}[-/ ]\w{2,4}[-/ ]\d{2,4}|\d{4}-\d{2}-\d{2})")


def _dec(v: Any, *, signed: bool = False) -> Decimal | None:
    """`signed` applies a trailing Dr/Cr marker as sign; debit/credit columns carry their own."""
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("₹", "").replace("INR", "").strip()
    if not s or s in {"-", "–"}:
        return None
    sign = -1 if signed and s.lower().rstrip(".").endswith("dr") else 1
    s = re.sub(r"(?i)\s*(cr|dr)\.?$", "", s)
    try:
        return Decimal(s) * sign
    except InvalidOperation as exc:
        raise StatementError(f"not a number: {v!r}") from exc


def _date(v: Any, formats: tuple[str, ...]) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for f in formats:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise StatementError(f"unparseable date: {v!r}")


def _is_data_row(r: dict[str, Any], mapping: ColumnMapping) -> bool:
    """Skip preamble/summary/separator rows ('Opening Balance', '****', narration wrap-arounds)."""
    v = r.get(normalise_header(mapping.date))
    if isinstance(v, (date, datetime)):
        return True
    return bool(v) and DATE_ONLY.match(str(v)) is not None


def read_rows(
    data: bytes, fmt: str, *, password: str | None = None
) -> tuple[list[dict[str, Any]], ColumnMapping | None]:
    """Rows keyed by normalised header, plus the mapping whose header row was found (if any)."""
    required = [
        (normalise_header(m.date), normalise_header(m.description)) for m in MAPPINGS.values()
    ]
    grid = read_grid(data, fmt, password=password, required=required)
    idx = find_header(grid, required)
    if idx is None:
        if not grid:
            return [], None
        return grid_to_rows(grid, 0), None
    rows = grid_to_rows(grid, idx)
    return rows, detect_mapping(set(rows[0].keys())) if rows else None


def detect_mapping(headers: set[str]) -> ColumnMapping:
    for m in MAPPINGS.values():
        if normalise_header(m.date) in headers and normalise_header(m.description) in headers:
            return m
    raise StatementError(f"No bank mapping matches columns: {sorted(h for h in headers if h)}")


@dataclass(frozen=True)
class ParsedRow:
    date: date
    amount: Decimal
    description: str
    reference: str
    balance_after: Decimal | None
    sha256: str


def parse_rows(
    rows: list[dict[str, Any]], mapping: ColumnMapping, account_id: str
) -> list[ParsedRow]:
    col = {
        name: normalise_header(getattr(mapping, name))
        for name in ("date", "description", "reference", "amount", "debit", "credit", "balance")
        if getattr(mapping, name)
    }
    out: list[ParsedRow] = []
    for r in rows:
        if not _is_data_row(r, mapping):
            continue
        d = _date(r.get(col["date"]), mapping.date_formats)
        desc = str(r.get(col["description"]) or "").strip()
        ref = str(r.get(col["reference"]) or "").strip() if "reference" in col else ""
        if "amount" in col and r.get(col["amount"]) not in (None, ""):
            amount = _dec(r.get(col["amount"]), signed=True) or Decimal("0")
        else:
            debit = _dec(r.get(col["debit"])) if "debit" in col else None
            credit = _dec(r.get(col["credit"])) if "credit" in col else None
            amount = (credit or Decimal("0")) - (debit or Decimal("0"))
        bal = _dec(r.get(col["balance"])) if "balance" in col else None
        key = f"{account_id}|{d.isoformat()}|{amount}|{desc}|{ref}"
        out.append(
            ParsedRow(
                d, amount, desc[:500], ref[:100], bal, hashlib.sha256(key.encode()).hexdigest()
            )
        )
    return out


def import_statement(
    account: BankAccount,
    *,
    data: bytes,
    filename: str,
    fmt: str,
    actor: Any = None,
    mapping_key: str | None = None,
    password: str | None = None,
) -> BankStatementImport:
    rows, detected = read_rows(data, fmt, password=password)
    if not rows:
        raise StatementError("No rows found.")
    if mapping_key:
        mapping = MAPPINGS[mapping_key]
    else:
        mapping = detected or detect_mapping(set(rows[0].keys()))
    parsed = parse_rows(rows, mapping, str(account.pk))
    if not parsed:
        raise StatementError(
            "Found the header row but no transaction rows under it — "
            f"expected dates in the '{mapping.date}' column."
        )
    with transaction.atomic():
        imp = BankStatementImport.objects.create(
            bank_account=account,
            filename=filename[:255],
            format=fmt,
            mapping=mapping.key,
            rows_total=len(parsed),
            created_by=actor if getattr(actor, "pk", None) else None,
        )
        imported = dup = 0
        latest: ParsedRow | None = None
        for p in parsed:
            try:
                with transaction.atomic():
                    BankTransaction.objects.create(
                        bank_account=account,
                        statement_import=imp,
                        date=p.date,
                        amount=p.amount,
                        description=p.description,
                        reference=p.reference,
                        balance_after=p.balance_after,
                        sha256=p.sha256,
                    )
                imported += 1
            except IntegrityError:
                dup += 1
            if p.balance_after is not None and (latest is None or p.date >= latest.date):
                latest = p
        imp.rows_imported, imp.rows_duplicate = imported, dup
        imp.save(update_fields=["rows_imported", "rows_duplicate", "updated_at"])
        if latest is not None:
            BankBalanceSnapshot.objects.get_or_create(
                org=account.org,
                bank_account=account,
                date=latest.date,
                source="statement",
                defaults={"balance": latest.balance_after},
            )
    return imp
