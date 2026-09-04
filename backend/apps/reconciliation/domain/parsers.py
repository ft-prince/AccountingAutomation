"""Pure parsers for the two GSTN GSTR-2B download formats (PROJECT_SPECS §3.8, §7.2).

JSON  (GSTN "GSTR2B" download):
  {"data": {"gstin", "rtnprd" "MMYYYY", "docdata": {"b2b": [
      {"ctin", "trdnm", "inv": [{"inum", "idt" DD-MM-YYYY, "val", "pos", "rev" Y/N,
                                  "itcavl" Y/N, "txval", "igst", "cgst", "sgst", "cess"}]}]}}}
Excel (GSTN "GSTR-2B" workbook, sheet "B2B"):
  a title block, then a header row containing "Invoice number" (found by scanning the
  first HEADER_SCAN_ROWS rows, case-insensitive), then one row per invoice *per rate*
  with "(₹)" suffix variants on the amount columns. Rows sharing (GSTIN, number, date)
  are aggregated into one record: amounts summed, invoice value taken once.

No I/O here: callers hand in the decoded JSON object or the sheet rows.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

HEADER_SCAN_ROWS = 10
HEADER_ANCHOR = "invoice number"
DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")
TWO_DP = Decimal("0.01")
ZERO = Decimal("0")

# Normalised header → field. Matching is prefix-based so "Invoice Value(₹)" and
# "Invoice Value (Rs.)" both resolve. Order matters only for readability.
COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("gstin of supplier", "supplier_gstin", True),
    ("trade/legal name", "supplier_name", False),
    ("invoice number", "invoice_number", True),
    ("invoice date", "invoice_date", True),
    ("invoice value", "invoice_value", True),
    ("place of supply", "place_of_supply", False),
    ("supply attract reverse charge", "reverse_charge", False),
    ("taxable value", "taxable_value", True),
    ("integrated tax", "igst", True),
    ("central tax", "cgst", True),
    ("state/ut tax", "sgst", True),
    ("cess", "cess", True),
    ("itc availability", "itc_available", True),
)
_CURRENCY_SUFFIX = re.compile(r"\(\s*(₹|rs\.?|inr)\s*\)|₹", re.IGNORECASE)
_SPACES = re.compile(r"\s+")
_TRUTHY = {"y", "yes", "true", "1"}
_POS_CODE = re.compile(r"^\d{2}")


class Parse2BError(ValueError):
    """The upload is not a GSTR-2B we understand. Message is safe to show the user."""


@dataclass(frozen=True)
class Parsed2BRecord:
    supplier_gstin: str
    supplier_name: str
    invoice_number: str
    invoice_date: date
    invoice_value: Decimal
    place_of_supply: str
    reverse_charge: bool
    taxable_value: Decimal
    igst: Decimal
    cgst: Decimal
    sgst: Decimal
    cess: Decimal
    itc_available: bool
    raw: dict[str, object]

    @property
    def tax(self) -> Decimal:
        return self.igst + self.cgst + self.sgst + self.cess


def to_money(value: object) -> Decimal:
    """Decimal(2dp, HALF_UP) from a JSON number, an Excel cell or a formatted string.
    Floats only ever arrive from openpyxl/json.loads; `Decimal(str(x))` is the boundary."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, bool):
        raise Parse2BError(f"expected an amount, got {value!r}")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int | float):
        amount = Decimal(str(value))
    else:
        cleaned = str(value).replace(",", "").replace("₹", "").strip()
        try:
            amount = Decimal(cleaned)
        except InvalidOperation as exc:
            raise Parse2BError(f"expected an amount, got {value!r}") from exc
    return amount.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def to_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise Parse2BError(f"unrecognised date {value!r}")


def to_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


def to_pos(value: object) -> str:
    """Place of supply as a two-digit state code; Excel writes "27-Maharashtra"."""
    match = _POS_CODE.match(str(value or "").strip())
    return match.group(0) if match else ""


def _as_dict(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Parse2BError(f"{where} must be an object")
    return {str(k): v for k, v in value.items()}


def _as_list(value: object, where: str) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise Parse2BError(f"{where} must be a list")
    return list(value)


def _record_from_json(supplier: dict[str, object], inv: dict[str, object]) -> Parsed2BRecord:
    return Parsed2BRecord(
        supplier_gstin=str(supplier.get("ctin", "")).strip().upper(),
        supplier_name=str(supplier.get("trdnm", "") or ""),
        invoice_number=str(inv.get("inum", "")).strip(),
        invoice_date=to_date(inv.get("idt")),
        invoice_value=to_money(inv.get("val")),
        place_of_supply=to_pos(inv.get("pos")),
        reverse_charge=to_flag(inv.get("rev", "N")),
        taxable_value=to_money(inv.get("txval")),
        igst=to_money(inv.get("igst")),
        cgst=to_money(inv.get("cgst")),
        sgst=to_money(inv.get("sgst")),
        cess=to_money(inv.get("cess")),
        itc_available=to_flag(inv.get("itcavl", "N")),
        raw=dict(inv),
    )


def parse_2b_json(payload: object) -> tuple[str, list[Parsed2BRecord]]:
    """(rtnprd, records) from the decoded GSTN 2B JSON. rtnprd is "" when absent."""
    root = _as_dict(payload, "root")
    data = _as_dict(root.get("data"), "data")
    docdata = _as_dict(data.get("docdata", {}), "docdata")
    records: list[Parsed2BRecord] = []
    for supplier_obj in _as_list(docdata.get("b2b"), "b2b"):
        supplier = _as_dict(supplier_obj, "b2b[]")
        for inv_obj in _as_list(supplier.get("inv"), "inv"):
            inv = _as_dict(inv_obj, "inv[]")
            if not str(inv.get("inum", "")).strip():
                raise Parse2BError(f"invoice without inum under {supplier.get('ctin')!r}")
            records.append(_record_from_json(supplier, inv))
    return str(data.get("rtnprd", "") or ""), records


def normalise_header(cell: object) -> str:
    text = _CURRENCY_SUFFIX.sub("", str(cell or "")).lower()
    return _SPACES.sub(" ", text).strip()


def find_header_row(rows: Sequence[Sequence[object]]) -> int:
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        if any(HEADER_ANCHOR in normalise_header(cell) for cell in row):
            return index
    raise Parse2BError(
        f"no header row containing {HEADER_ANCHOR!r} in the first "
        f"{HEADER_SCAN_ROWS} rows of sheet B2B"
    )


def map_columns(header: Sequence[object]) -> dict[str, int]:
    """field → column index. Required columns missing → Parse2BError naming them."""
    normalised = [normalise_header(cell) for cell in header]
    mapping: dict[str, int] = {}
    for prefix, field, _required in COLUMNS:
        for index, name in enumerate(normalised):
            if name.startswith(prefix) and index not in mapping.values():
                mapping[field] = index
                break
    missing = [prefix for prefix, field, required in COLUMNS if required and field not in mapping]
    if missing:
        raise Parse2BError(f"sheet B2B is missing columns: {', '.join(missing)}")
    return mapping


def _cell(row: Sequence[object], mapping: dict[str, int], field: str) -> object:
    index = mapping.get(field)
    if index is None or index >= len(row):
        return None
    return row[index]


def _record_from_row(row: Sequence[object], mapping: dict[str, int]) -> Parsed2BRecord:
    raw = {field: _cell(row, mapping, field) for field in mapping}
    return Parsed2BRecord(
        supplier_gstin=str(raw["supplier_gstin"]).strip().upper(),
        supplier_name=str(raw.get("supplier_name") or ""),
        invoice_number=str(raw["invoice_number"]).strip(),
        invoice_date=to_date(raw["invoice_date"]),
        invoice_value=to_money(raw["invoice_value"]),
        place_of_supply=to_pos(raw.get("place_of_supply")),
        reverse_charge=to_flag(raw.get("reverse_charge") or "N"),
        taxable_value=to_money(raw["taxable_value"]),
        igst=to_money(raw["igst"]),
        cgst=to_money(raw["cgst"]),
        sgst=to_money(raw["sgst"]),
        cess=to_money(raw["cess"]),
        itc_available=to_flag(raw["itc_available"]),
        raw={k: _jsonable(v) for k, v in raw.items()},
    )


def _jsonable(value: object) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _merge(first: Parsed2BRecord, other: Parsed2BRecord) -> Parsed2BRecord:
    return replace(
        first,
        taxable_value=first.taxable_value + other.taxable_value,
        igst=first.igst + other.igst,
        cgst=first.cgst + other.cgst,
        sgst=first.sgst + other.sgst,
        cess=first.cess + other.cess,
        itc_available=first.itc_available and other.itc_available,
    )


def parse_2b_rows(rows: Sequence[Sequence[object]]) -> list[Parsed2BRecord]:
    """Records from the B2B sheet's rows (header detection + per-rate aggregation)."""
    header_index = find_header_row(rows)
    mapping = map_columns(rows[header_index])
    merged: dict[tuple[str, str, date], Parsed2BRecord] = {}
    for row in rows[header_index + 1 :]:
        gstin = _cell(row, mapping, "supplier_gstin")
        number = _cell(row, mapping, "invoice_number")
        if not str(gstin or "").strip() or not str(number or "").strip():
            continue
        record = _record_from_row(row, mapping)
        key = (record.supplier_gstin, record.invoice_number, record.invoice_date)
        merged[key] = _merge(merged[key], record) if key in merged else record
    return list(merged.values())
