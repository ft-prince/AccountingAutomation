"""Pure GSTR-2B ↔ books matching rules (PROJECT_SPECS §7.2, §3.8).

Match types: exact | fuzzy | value_mismatch | missing_in_books | missing_in_2b.
Tolerances are data, not if-statements.

  exact          normalised number equal AND |Δtotal| ≤ ₹1 AND same date
  fuzzy          |Δtotal| ≤ ₹1 AND (normalised number equal OR |Δdays| ≤ 3)
  value_mismatch normalised number equal AND |Δtotal| > ₹1 (deltas stored)
  missing_in_books  2B record with no candidate
  missing_in_2b     confirmed inward invoice (GSTIN-bearing party) with no record

Number normalisation: uppercase, drop spaces and every non-alphanumeric except
"/" and "-", strip leading zeros from each digit run ("INV-001" == "inv 1").
"/" and "-" are deliberately kept, so "INV/001" vs "INV-001" is *not* an
exact match; it falls to fuzzy through the date rule when the values agree.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

VALUE_TOLERANCE = Decimal("1.00")
DATE_TOLERANCE_DAYS = 3

MatchType = Literal["exact", "fuzzy", "value_mismatch", "missing_in_books", "missing_in_2b"]
EXACT: MatchType = "exact"
FUZZY: MatchType = "fuzzy"
VALUE_MISMATCH: MatchType = "value_mismatch"
MISSING_IN_BOOKS: MatchType = "missing_in_books"
MISSING_IN_2B: MatchType = "missing_in_2b"
MATCH_TYPES: tuple[MatchType, ...] = (EXACT, FUZZY, VALUE_MISMATCH, MISSING_IN_BOOKS, MISSING_IN_2B)

_PRIORITY: dict[str, int] = {EXACT: 0, FUZZY: 1, VALUE_MISMATCH: 2}
_DROP = re.compile(r"[^A-Z0-9/\-]")
_LEADING_ZEROS = re.compile(r"(?<![0-9])0+(?=[0-9])")
ZERO = Decimal("0")


def normalise_invoice_number(raw: str) -> str:
    return _LEADING_ZEROS.sub("", _DROP.sub("", raw.upper()))


@dataclass(frozen=True)
class MatchSide:
    """The fields matching looks at, from either a 2B record or a book invoice."""

    key: str
    gstin: str
    invoice_number: str
    invoice_date: date
    total: Decimal
    tax: Decimal


@dataclass(frozen=True)
class PairOutcome:
    match_type: MatchType
    delta_value: Decimal
    delta_tax: Decimal
    rank: tuple[int, int, int, Decimal]  # lower is better


@dataclass(frozen=True)
class Pair:
    record_key: str
    invoice_key: str
    outcome: PairOutcome


@dataclass(frozen=True)
class MatchResult:
    pairs: tuple[Pair, ...]
    missing_in_books: tuple[str, ...]  # record keys
    missing_in_2b: tuple[str, ...]  # invoice keys


def classify_pair(record: MatchSide, invoice: MatchSide) -> PairOutcome | None:
    """Outcome for one record/invoice pair, or None when they cannot be the same document."""
    if record.gstin != invoice.gstin:
        return None
    number_equal = normalise_invoice_number(record.invoice_number) == normalise_invoice_number(
        invoice.invoice_number
    )
    day_gap = abs((record.invoice_date - invoice.invoice_date).days)
    delta_value = record.total - invoice.total
    delta_tax = record.tax - invoice.tax
    value_ok = abs(delta_value) <= VALUE_TOLERANCE
    if number_equal and value_ok and day_gap == 0:
        match_type: MatchType = EXACT
    elif value_ok and (number_equal or day_gap <= DATE_TOLERANCE_DAYS):
        match_type = FUZZY
    elif number_equal:
        match_type = VALUE_MISMATCH
    else:
        return None
    rank = (_PRIORITY[match_type], 0 if number_equal else 1, day_gap, abs(delta_value))
    return PairOutcome(match_type, delta_value, delta_tax, rank)


def match_records(
    records: tuple[MatchSide, ...],
    invoices: tuple[MatchSide, ...],
    period_invoice_keys: frozenset[str],
) -> MatchResult:
    """Greedy one-to-one assignment, best-ranked pairs first, so an exact match is never
    stolen by another record's fuzzy candidate. `period_invoice_keys` are the invoices that
    belong to the batch period itself (candidates include ±3 days of slack around it);
    only those are reported as missing_in_2b."""
    candidates: list[tuple[tuple[int, int, int, Decimal], int, int, Pair]] = []
    for r_index, record in enumerate(records):
        for i_index, invoice in enumerate(invoices):
            outcome = classify_pair(record, invoice)
            if outcome is not None:
                pair = Pair(record.key, invoice.key, outcome)
                candidates.append((outcome.rank, r_index, i_index, pair))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    used_records: set[str] = set()
    used_invoices: set[str] = set()
    pairs: list[Pair] = []
    for _rank, _r, _i, pair in candidates:
        if pair.record_key in used_records or pair.invoice_key in used_invoices:
            continue
        used_records.add(pair.record_key)
        used_invoices.add(pair.invoice_key)
        pairs.append(pair)
    missing_in_books = tuple(r.key for r in records if r.key not in used_records)
    missing_in_2b = tuple(
        i.key for i in invoices if i.key not in used_invoices and i.key in period_invoice_keys
    )
    return MatchResult(tuple(pairs), missing_in_books, missing_in_2b)


def itc_at_risk(match_type: str, record_tax: Decimal, delta_tax: Decimal) -> Decimal:
    """Tax exposed by one match row: the disputed tax on a value mismatch and the whole 2B
    tax on a record the books never claimed. Other types carry no risk."""
    if match_type == VALUE_MISMATCH:
        return abs(delta_tax)
    if match_type == MISSING_IN_BOOKS:
        return record_tax
    return ZERO
