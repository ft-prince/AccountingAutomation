import Big from "big.js";

// Payment → invoice allocation arithmetic (PROJECT_SPECS §4 payments). All amounts are decimal
// strings; big.js keeps paise exact. The server's Decimal result is authoritative.

export interface AllocationDraft {
  invoice: string;
  amount: string; // "" while the user has not typed anything
}

const ZERO = new Big(0);

function toBig(value: string): Big {
  const trimmed = value.trim();
  if (trimmed === "" || trimmed === "-" || trimmed === ".") return ZERO;
  try {
    return new Big(trimmed);
  } catch {
    return ZERO;
  }
}

export function sumAllocations(items: readonly AllocationDraft[]): string {
  return items.reduce((total, item) => total.plus(toBig(item.amount)), ZERO).toFixed(2);
}

/** Payment amount minus everything allocated so far. Negative means over-allocated. */
export function allocationRemainder(paymentAmount: string, items: readonly AllocationDraft[]): string {
  return toBig(paymentAmount).minus(new Big(sumAllocations(items))).toFixed(2);
}

export function isOverAllocated(paymentAmount: string, items: readonly AllocationDraft[]): boolean {
  return new Big(allocationRemainder(paymentAmount, items)).lt(0);
}

export function hasNegativeAllocation(items: readonly AllocationDraft[]): boolean {
  return items.some((item) => toBig(item.amount).lt(0));
}

/** Only items with a positive amount are sent to the API. */
export function allocationsToSubmit(items: readonly AllocationDraft[]): { invoice: string; amount: string }[] {
  return items.filter((item) => toBig(item.amount).gt(0)).map((item) => ({ invoice: item.invoice, amount: toBig(item.amount).toFixed(2) }));
}

/** The larger of zero and min(outstanding, remainder) — what "fill" should put in a row. */
export function suggestedAllocation(outstanding: string, remainder: string): string {
  const cap = toBig(outstanding);
  const left = toBig(remainder);
  if (left.lte(0) || cap.lte(0)) return "0.00";
  return (cap.lt(left) ? cap : left).toFixed(2);
}
