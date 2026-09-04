// Display formatting for dates, months and enum labels. Money lives in lib/money.ts.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-09-04" → "4 Sep 2026". Non-ISO input is returned unchanged. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

/** "2026-04" → "Apr 2026". */
export function formatMonth(yearMonth: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(yearMonth);
  if (!match) return yearMonth;
  return `${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

/** "needs_review" → "Needs review". */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  const text = value.replace(/[_-]+/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatBytes(bytes: number): string {
  const KB = 1024;
  if (bytes < KB) return `${bytes} B`;
  if (bytes < KB * KB) return `${(bytes / KB).toFixed(0)} KB`;
  return `${(bytes / (KB * KB)).toFixed(1)} MB`;
}

/** "2026-09" for a YYYY-MM-DD date. */
export function yearMonthOf(iso: string): string {
  return iso.slice(0, 7);
}
