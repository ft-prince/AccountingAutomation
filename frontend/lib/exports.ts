// PROJECT_SPECS §10 Exports — GET /api/exports/{gstr1|gstr3b|csv}. Plain download links; the browser
// follows them with the session cookie, so no fetch wrapper is needed.
import { buildQuery } from "@/lib/query";

export const CSV_EXPORT_TYPES = ["tally", "zoho", "raw"] as const;
export type CsvExportType = (typeof CSV_EXPORT_TYPES)[number];

const MONTH_PATTERN = /^(\d{4})-(\d{2})-\d{2}$/;

/** "2026-08-15" → "082026", the MMYYYY form the GST portal and the export API use. */
export function toGstPeriod(isoDate: string): string {
  const match = MONTH_PATTERN.exec(isoDate);
  if (!match) throw new Error(`Expected YYYY-MM-DD, got "${isoDate}"`);
  return `${match[2]}${match[1]}`;
}

export function gstr1ExportUrl(period: string): string {
  return `/api/exports/gstr1${buildQuery({ period })}`;
}

export function gstr3bExportUrl(period: string): string {
  return `/api/exports/gstr3b${buildQuery({ period })}`;
}

export function csvExportUrl(type: CsvExportType, range?: { from: string; to: string }): string {
  return `/api/exports/csv${buildQuery({ type, from: range?.from, to: range?.to })}`;
}
