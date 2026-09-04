"""Pure text extraction shared by party resolution and guardrails. PROJECT_SPECS §6.5.
No Django, no I/O. Every extractor returns normalised, de-duplicated values."""

import re
from decimal import Decimal

GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
# INV-0042, NX/2026-27/0042, RIOT-2026-0042 — letters, optional separator, digits, suffixes.
INVOICE_TOKEN_RE = re.compile(r"\b(?!FY\d)[A-Z]{2,6}[-/]?\d{2,}(?:[-/][A-Z0-9]+)*\b")
# Currency-prefixed number, or a number with grouping commas / two decimals.
MONEY_RE = re.compile(
    r"(?:₹|\b(?:Rs\.?|INR))\s*(\d[\d,]*(?:\.\d+)?)"
    r"|(?<![\d.,])(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?)(?![\d.,])"
    r"|(?<![\d.,])(\d+\.\d{2})(?![\d.,])"
)
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
MONTH_ALT = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*"
DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_DMY_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b")
DATE_D_MON_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_ALT})\.?,?(?:\s+(\d{{4}}))?\b", re.I
)
DATE_MON_D_RE = re.compile(
    rf"\b({MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?(?:\s+(\d{{4}}))?\b", re.I
)
TWO_DIGIT_YEAR_BASE = 2000


def normalize_amount(raw: str) -> str:
    """'1,18,000' → '118000.00'. Callers pass digits/commas/one point only (MONEY_RE)."""
    return str(Decimal(raw.replace(",", "")).quantize(Decimal("0.01")))


def find_money(text: str) -> set[str]:
    return {
        normalize_amount(next(g for g in match.groups() if g is not None))
        for match in MONEY_RE.finditer(text)
    }


def normalize_invoice_number(raw: str) -> str:
    return re.sub(r"\s+", "", raw).upper()


def find_invoice_numbers(text: str) -> set[str]:
    """Invoice-number-like tokens, excluding IFSC codes and GSTINs."""
    out: set[str] = set()
    for match in INVOICE_TOKEN_RE.finditer(text.upper()):
        token = match.group(0)
        if IFSC_RE.fullmatch(token) or GSTIN_RE.fullmatch(token):
            continue
        out.add(normalize_invoice_number(token))
    return out


def find_gstins(text: str) -> set[str]:
    return set(GSTIN_RE.findall(text.upper()))


def _month_number(name: str) -> int:
    """The regex only admits known month prefixes, so a lookup always succeeds."""
    return MONTHS.get(name.lower()[:4]) or MONTHS[name.lower()[:3]]


def _iso(year: int | None, month: int, day: int) -> str | None:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    if year is None:
        return f"{month:02d}-{day:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}"


def _year(raw: str | None) -> int | None:
    if raw is None:
        return None
    year = int(raw)
    return year + TWO_DIGIT_YEAR_BASE if year < 100 else year


def find_dates(text: str) -> set[str]:
    """Dates as 'YYYY-MM-DD', or 'MM-DD' when the year is absent. Day-first (India)."""
    out: set[str] = set()
    for m in DATE_ISO_RE.finditer(text):
        iso = _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if iso is not None:
            out.add(iso)
    for m in DATE_DMY_RE.finditer(text):
        iso = _iso(_year(m.group(3)), int(m.group(2)), int(m.group(1)))
        if iso is not None:
            out.add(iso)
    for m in DATE_D_MON_RE.finditer(text):
        iso = _iso(_year(m.group(3)), _month_number(m.group(2)), int(m.group(1)))
        if iso is not None:
            out.add(iso)
    for m in DATE_MON_D_RE.finditer(text):
        iso = _iso(_year(m.group(3)), _month_number(m.group(1)), int(m.group(2)))
        if iso is not None:
            out.add(iso)
    return out


def date_forms(iso_dates: set[str]) -> set[str]:
    """Snapshot dates plus their year-less 'MM-DD' forms so 'by 14 Aug' can match."""
    out = set(iso_dates)
    for iso in iso_dates:
        parts = iso.split("-")
        if len(parts) == 3:
            out.add(f"{parts[1]}-{parts[2]}")
    return out
