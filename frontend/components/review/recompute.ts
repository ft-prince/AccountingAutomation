// Client-side mirror of apps/gst/domain/tax.py (PROJECT_SPECS §3.9) for instant feedback.
// Strings in, strings out via big.js; the server's Decimal result is authoritative.
import Big from "big.js";

Big.RM = Big.roundHalfUp;

export type SupplyType = "intra" | "inter" | "export" | "sez" | "import";

export interface LineInput {
  quantity: string;
  unit_price: string;
  discount: string;
  rate: string;
  cess_rate: string;
}

export interface LineComputed {
  taxable_value: string;
  cgst: string;
  sgst: string;
  igst: string;
  cess: string;
  line_total: string;
}

export interface InvoiceTotals {
  taxable_value: string;
  cgst: string;
  sgst: string;
  igst: string;
  cess: string;
  round_off: string;
  total: string;
}

const PAISE = 2;
const RUPEE = 0;
const HUNDRED = new Big(100);
const TWO_HUNDRED = new Big(200);
const ZERO = new Big(0);

const DECIMAL_RE = /^-?(\d+(\.\d*)?|\.\d+)$/;

/** Lenient parse for half-typed inputs: "", "12.", "-" → usable values; garbage → 0. */
export function toBig(value: string | null | undefined): Big {
  if (value === null || value === undefined) return ZERO;
  const trimmed = value.trim();
  if (!DECIMAL_RE.test(trimmed)) return ZERO;
  return new Big(trimmed.endsWith(".") ? `${trimmed}0` : trimmed);
}

export function isDecimalString(value: string): boolean {
  return DECIMAL_RE.test(value.trim()) && !value.trim().endsWith(".");
}

function money(value: Big): string {
  return value.round(PAISE, Big.roundHalfUp).toFixed(PAISE);
}

export function usesIgst(supplyType: SupplyType): boolean {
  return supplyType !== "intra";
}

/** taxable = unit_price×qty − discount; heads per §3.2; cess; line_total. */
export function computeLine(line: LineInput, supplyType: SupplyType): LineComputed {
  const taxable = toBig(line.unit_price).times(toBig(line.quantity)).minus(toBig(line.discount)).round(PAISE);
  const rate = toBig(line.rate);
  const cess = taxable.times(toBig(line.cess_rate)).div(HUNDRED).round(PAISE);
  const heads = usesIgst(supplyType)
    ? { cgst: ZERO, sgst: ZERO, igst: taxable.times(rate).div(HUNDRED).round(PAISE) }
    : (() => {
        const half = taxable.times(rate).div(TWO_HUNDRED).round(PAISE);
        return { cgst: half, sgst: half, igst: ZERO };
      })();
  const lineTotal = taxable.plus(heads.cgst).plus(heads.sgst).plus(heads.igst).plus(cess);
  return {
    taxable_value: money(taxable),
    cgst: money(heads.cgst),
    sgst: money(heads.sgst),
    igst: money(heads.igst),
    cess: money(cess),
    line_total: money(lineTotal),
  };
}

function sumOf(lines: readonly LineComputed[], key: keyof LineComputed): Big {
  return lines.reduce((acc, line) => acc.plus(new Big(line[key])), ZERO);
}

/** Σ lines, invoice total rounded to the rupee HALF_UP, delta stored as round_off. */
export function computeTotals(lines: readonly LineComputed[]): InvoiceTotals {
  const exact = sumOf(lines, "line_total");
  const total = exact.round(RUPEE, Big.roundHalfUp);
  return {
    taxable_value: money(sumOf(lines, "taxable_value")),
    cgst: money(sumOf(lines, "cgst")),
    sgst: money(sumOf(lines, "sgst")),
    igst: money(sumOf(lines, "igst")),
    cess: money(sumOf(lines, "cess")),
    round_off: money(total.minus(exact)),
    total: money(total),
  };
}

export function computeInvoice(lines: readonly LineInput[], supplyType: SupplyType): { lines: LineComputed[]; totals: InvoiceTotals } {
  const computed = lines.map((line) => computeLine(line, supplyType));
  return { lines: computed, totals: computeTotals(computed) };
}

/** True when two decimal strings denote the same amount ("900" vs "900.00"). */
export function sameAmount(a: string | undefined, b: string | undefined): boolean {
  if (a === undefined || b === undefined) return a === b;
  return toBig(a).eq(toBig(b));
}
