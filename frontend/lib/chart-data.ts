// Pure helpers that reshape §7.2 report rows for Recharts. Recharts needs JS numbers for geometry
// (bar heights, pie angles); those numbers are used ONLY to draw. Every label, tooltip and axis tick
// is formatted from the original decimal string, so no rupee is ever rounded through a float.
import Big from "big.js";
import { orZero } from "@/lib/money";

export const MAX_DONUT_SLICES = 5;
export const OTHER_LABEL = "Other";

/** Geometry-only conversion. Never use the result for arithmetic or display. */
export function toChartNumber(decimal: string | null | undefined): number {
  return Number(orZero(decimal));
}

export interface DonutSlice {
  name: string;
  amount: string;
  value: number;
}

/** Top `max` categories by amount plus a single "Other" slice for the rest (§7.4 row 3). */
export function donutSlices(rows: readonly { category: string; amount: string }[], max = MAX_DONUT_SLICES): DonutSlice[] {
  const sorted = [...rows].filter((row) => new Big(orZero(row.amount)).gt(0)).sort((a, b) => new Big(b.amount).cmp(new Big(a.amount)));
  if (sorted.length <= max) return sorted.map((row) => ({ name: row.category, amount: row.amount, value: toChartNumber(row.amount) }));
  const head = sorted.slice(0, max);
  const rest = sorted.slice(max).reduce((total, row) => total.plus(new Big(row.amount)), new Big(0)).toFixed(2);
  return [...head.map((row) => ({ name: row.category, amount: row.amount, value: toChartNumber(row.amount) })), { name: OTHER_LABEL, amount: rest, value: toChartNumber(rest) }];
}

export interface PnlPoint {
  month: string;
  revenue: number;
  expenses: number;
  net: number;
  revenueText: string;
  expensesText: string;
  netText: string;
}

/** Revenue vs total expenses (COGS + opex) per month; net kept for the tooltip. */
export function pnlPoints(rows: readonly { month: string; revenue: string; cogs: string; opex: string; net: string }[]): PnlPoint[] {
  return rows.map((row) => {
    const expenses = new Big(orZero(row.cogs)).plus(new Big(orZero(row.opex))).toFixed(2);
    return {
      month: row.month,
      revenue: toChartNumber(row.revenue),
      expenses: toChartNumber(expenses),
      net: toChartNumber(row.net),
      revenueText: orZero(row.revenue),
      expensesText: expenses,
      netText: orZero(row.net),
    };
  });
}

export interface ShareBarPoint {
  name: string;
  amount: number;
  amountText: string;
  sharePct: string;
}

export function shareBarPoints(rows: readonly { name: string; amount: string; share_pct: string }[], limit: number): ShareBarPoint[] {
  return rows.slice(0, limit).map((row) => ({ name: row.name, amount: toChartNumber(row.amount), amountText: orZero(row.amount), sharePct: row.share_pct }));
}
