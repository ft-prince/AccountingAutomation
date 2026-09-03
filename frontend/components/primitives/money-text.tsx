import { abbreviateINR, formatINR } from "@/lib/money";
import { cn } from "@/lib/utils";

export interface MoneyTextProps {
  /** Decimal string from the API ("123456.78"). Never a number — floats lose paise. */
  value: string;
  /** Lakh / crore abbreviation for axes and tiles ("₹1.25Cr"). */
  abbreviate?: boolean;
  className?: string;
}

export function MoneyText({ value, abbreviate = false, className }: MoneyTextProps) {
  if (typeof value !== "string") {
    throw new TypeError("MoneyText requires a decimal string; numbers are not permitted (CLAUDE.md §4).");
  }
  const text = abbreviate ? abbreviateINR(value) : formatINR(value);
  return (
    <span className={cn("tabular-nums", className)} title={abbreviate ? formatINR(value) : undefined}>
      {text}
    </span>
  );
}
