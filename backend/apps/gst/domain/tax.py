"""Tax heads, line arithmetic and the rate table (PROJECT_SPECS §3.2, §3.3, §3.9).

All money is Decimal quantised to paise with ROUND_HALF_UP. Never float.
Rates are DATA with effective-date ranges (§3.3), never constants in logic.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from apps.gst.domain.supply import SupplyType

PAISE = Decimal("0.01")
RUPEE = Decimal("1")
HUNDRED = Decimal("100")
TWO_HUNDRED = Decimal("200")
ZERO_PAISE = Decimal("0.00")

GST_START = date(2017, 7, 1)
GST_2_START = date(2025, 9, 22)
GST_1_END = date(2025, 9, 21)
TOBACCO_COMP_CESS_END = date(2026, 1, 31)
TOBACCO_40_START = date(2026, 2, 1)

TOBACCO_HSN_PREFIX = "24"
BIDI_HSN_PREFIX = "24031921"
# §3.3 only states "28% + comp cess"; the ad-valorem percentage differs per tobacco HSN.
# Seeded with the pan masala / chewing tobacco style ad-valorem figure so the row carries a
# non-zero cess, but the exact figure per HSN must be verified at go-live.
HISTORICAL_TOBACCO_COMP_CESS_RATE = Decimal("60")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def quantize_rupee(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxHeads:
    cgst: Decimal
    sgst: Decimal
    igst: Decimal


@dataclass(frozen=True)
class LineTax:
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class InvoiceTotals:
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal
    round_off: Decimal
    total: Decimal


@dataclass(frozen=True)
class TaxRate:
    hsn_prefix: str | None
    rate: Decimal
    cess_rate: Decimal
    effective_from: date
    effective_to: date | None
    is_composition: bool = False

    def applies_to(self, on_date: date, hsn_prefix: str | None) -> bool:
        if on_date < self.effective_from:
            return False
        if self.effective_to is not None and on_date > self.effective_to:
            return False
        if self.hsn_prefix is None:
            return True
        return hsn_prefix is not None and hsn_prefix.startswith(self.hsn_prefix)


def _general(rate: str, effective_from: date, effective_to: date | None) -> TaxRate:
    return TaxRate(None, Decimal(rate), Decimal("0"), effective_from, effective_to)


def _composition(rate: str) -> TaxRate:
    return TaxRate(None, Decimal(rate), Decimal("0"), GST_START, None, is_composition=True)


DEFAULT_RATE_TABLE: tuple[TaxRate, ...] = (
    # GST 1.0 slabs, valid to 21 Sep 2025
    _general("0", GST_START, GST_1_END),
    _general("5", GST_START, GST_1_END),
    _general("12", GST_START, GST_1_END),
    _general("18", GST_START, GST_1_END),
    _general("28", GST_START, GST_1_END),
    # GST 2.0 slabs, from 22 Sep 2025
    _general("0", GST_2_START, None),
    _general("5", GST_2_START, None),
    _general("18", GST_2_START, None),
    _general("40", GST_2_START, None),
    # Special rates: precious metals and rough diamonds, unchanged
    _general("3", GST_START, None),
    _general("0.25", GST_START, None),
    # Tobacco / pan masala: 28% + compensation cess historical, 40% with no comp cess after
    TaxRate(
        TOBACCO_HSN_PREFIX,
        Decimal("28"),
        HISTORICAL_TOBACCO_COMP_CESS_RATE,
        GST_START,
        TOBACCO_COMP_CESS_END,
    ),
    TaxRate(TOBACCO_HSN_PREFIX, Decimal("40"), Decimal("0"), TOBACCO_40_START, None),
    TaxRate(BIDI_HSN_PREFIX, Decimal("18"), Decimal("0"), GST_2_START, None),
    # Composition scheme: 1% manufacturers/traders, 5% restaurants, 6% other services
    _composition("1"),
    _composition("5"),
    _composition("6"),
)


def split_tax(taxable: Decimal, rate: Decimal, supply_type: SupplyType) -> TaxHeads:
    """Split tax into heads. Intra: CGST = SGST = round(taxable*rate/200, 2); else IGST.

    Each intra head is rounded independently so CGST always equals SGST; the paisa
    that can be lost against round(taxable*rate/100, 2) is absorbed by round_off.
    """
    if supply_type.uses_igst:
        return TaxHeads(ZERO_PAISE, ZERO_PAISE, quantize_money(taxable * rate / HUNDRED))
    half = quantize_money(taxable * rate / TWO_HUNDRED)
    return TaxHeads(half, half, ZERO_PAISE)


def compute_line(
    unit_price: Decimal,
    quantity: Decimal,
    discount: Decimal,
    rate: Decimal,
    cess_rate: Decimal,
    supply_type: SupplyType,
) -> LineTax:
    """§3.9: taxable = unit_price×qty − discount; line_total = taxable + heads + cess."""
    taxable = quantize_money(unit_price * quantity - discount)
    heads = split_tax(taxable, rate, supply_type)
    cess = quantize_money(taxable * cess_rate / HUNDRED)
    line_total = taxable + heads.cgst + heads.sgst + heads.igst + cess
    return LineTax(taxable, heads.cgst, heads.sgst, heads.igst, cess, line_total)


def compute_invoice_totals(lines: list[LineTax]) -> InvoiceTotals:
    """Sum lines, round the invoice total to the rupee, and store the delta as round_off."""
    taxable = sum((line.taxable for line in lines), ZERO_PAISE)
    cgst = sum((line.cgst for line in lines), ZERO_PAISE)
    sgst = sum((line.sgst for line in lines), ZERO_PAISE)
    igst = sum((line.igst for line in lines), ZERO_PAISE)
    cess = sum((line.cess for line in lines), ZERO_PAISE)
    exact = sum((line.line_total for line in lines), ZERO_PAISE)
    total = quantize_rupee(exact)
    return InvoiceTotals(taxable, cgst, sgst, igst, cess, quantize_money(total - exact), total)


def rate_valid_on(
    rate: Decimal,
    on_date: date,
    table: tuple[TaxRate, ...],
    hsn_prefix: str | None = None,
    *,
    is_composition: bool = False,
) -> bool:
    """True if any table entry with this rate applies on `on_date` for the given HSN."""
    return any(
        entry.rate == rate
        and entry.is_composition is is_composition
        and entry.applies_to(on_date, hsn_prefix)
        for entry in table
    )
