// Small display helpers local to the review screen.

const TIME_PAD = 2;

/** "hh:mm:ss" on the 24-hour clock for the "Saved · hh:mm:ss" indicator. */
export function formatClock(date: Date): string {
  const parts = [date.getHours(), date.getMinutes(), date.getSeconds()];
  return parts.map((part) => String(part).padStart(TIME_PAD, "0")).join(":");
}

/** "2026-08-06" → "06 Aug 2026"; anything else is echoed back. */
export function formatIsoDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${match[3]} ${months[Number(match[2]) - 1]} ${match[1]}`;
}

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
