import Big from "big.js";

// PROJECT_SPECS §9: Indian digit grouping, formatter takes a STRING, never a Number.
const LAKH = new Big("100000");
const CRORE = new Big("10000000");

function groupIndian(intPart: string): string {
  if (intPart.length <= 3) return intPart;
  const last3 = intPart.slice(-3);
  const rest = intPart.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${rest},${last3}`;
}

/** "123456.7" → "₹1,23,456.70" */
export function formatINR(amount: string, opts: { symbol?: boolean } = {}): string {
  const value = new Big(amount).toFixed(2);
  const negative = value.startsWith("-");
  const [intPart, frac] = (negative ? value.slice(1) : value).split(".");
  const symbol = opts.symbol === false ? "" : "₹";
  return `${negative ? "-" : ""}${symbol}${groupIndian(intPart)}.${frac}`;
}

/** Axis labels above 1,00,000: "250000" → "₹2.5L", "12500000" → "₹1.25Cr" */
export function abbreviateINR(amount: string): string {
  const v = new Big(amount);
  const abs = v.abs();
  const sign = v.lt(0) ? "-" : "";
  if (abs.gte(CRORE)) return `${sign}₹${trim(abs.div(CRORE).toFixed(2))}Cr`;
  if (abs.gte(LAKH)) return `${sign}₹${trim(abs.div(LAKH).toFixed(2))}L`;
  return formatINR(amount);
}

function trim(s: string): string {
  return s.replace(/\.?0+$/, "");
}
