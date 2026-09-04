// Every §10 invoice list query parameter, serialised in a stable order. Pure; no fetch.
import { buildQuery } from "@/lib/query";
import type { InvoiceDirection, InvoiceStatus, PaymentStatus } from "@/lib/types";

export type InvoiceOrdering =
  | "invoice_date"
  | "-invoice_date"
  | "total"
  | "-total"
  | "due_date"
  | "-due_date"
  | "confidence"
  | "-confidence"
  | "created_at"
  | "-created_at"
  | "party__legal_name"
  | "-party__legal_name";

export interface InvoiceFilters {
  status: InvoiceStatus | "";
  direction: InvoiceDirection | "";
  party: string;
  fy: string;
  period: string; // YYYY-MM
  payment_status: PaymentStatus | "";
  category: string;
  from: string;
  to: string;
  min: string;
  max: string;
  q: string;
  ordering: InvoiceOrdering;
}

export const EMPTY_INVOICE_FILTERS: InvoiceFilters = {
  status: "",
  direction: "",
  party: "",
  fy: "",
  period: "",
  payment_status: "",
  category: "",
  from: "",
  to: "",
  min: "",
  max: "",
  q: "",
  ordering: "-invoice_date",
};

export const INVOICE_PAGE_SIZE = 25;

export const SORTABLE_COLUMNS: readonly { id: string; field: Exclude<InvoiceOrdering, `-${string}`> }[] = [
  { id: "invoice_date", field: "invoice_date" },
  { id: "due_date", field: "due_date" },
  { id: "party_name", field: "party__legal_name" },
  { id: "total", field: "total" },
  { id: "confidence", field: "confidence" },
  { id: "created_at", field: "created_at" },
];

export interface InvoiceQueryOptions {
  cursor?: string | null;
  pageSize?: number;
}

/** "/api/invoices/?status=…&cursor=…" — omits empty filters. */
export function buildInvoicesQuery(filters: InvoiceFilters, options: InvoiceQueryOptions = {}): string {
  return buildQuery({
    status: filters.status,
    direction: filters.direction,
    party: filters.party,
    fy: filters.fy,
    period: filters.period,
    payment_status: filters.payment_status,
    category: filters.category,
    from: filters.from,
    to: filters.to,
    min: filters.min,
    max: filters.max,
    q: filters.q,
    ordering: filters.ordering,
    page_size: options.pageSize ?? INVOICE_PAGE_SIZE,
    cursor: options.cursor ?? undefined,
  });
}

export function invoicesListPath(filters: InvoiceFilters, options?: InvoiceQueryOptions): string {
  return `/api/invoices/${buildInvoicesQuery(filters, options)}`;
}

/** Server-side CSV of the same filtered set (may 404 until the exports endpoint lands). */
export function invoicesExportUrl(filters: InvoiceFilters): string {
  return `/api/exports/csv${buildQuery({
    type: "raw",
    status: filters.status,
    direction: filters.direction,
    party: filters.party,
    fy: filters.fy,
    period: filters.period,
    payment_status: filters.payment_status,
    category: filters.category,
    from: filters.from,
    to: filters.to,
    min: filters.min,
    max: filters.max,
    q: filters.q,
  })}`;
}

export function countActiveFilters(filters: InvoiceFilters): number {
  return (Object.keys(filters) as (keyof InvoiceFilters)[]).filter((key) => key !== "ordering" && filters[key] !== "").length;
}

/** Toggles sort on a column: none → desc → asc → desc … */
export function nextOrdering(current: InvoiceOrdering, field: Exclude<InvoiceOrdering, `-${string}`>): InvoiceOrdering {
  if (current === `-${field}`) return field;
  return `-${field}` as InvoiceOrdering;
}

const FILTER_KEYS = Object.keys(EMPTY_INVOICE_FILTERS) as (keyof InvoiceFilters)[];

/** Reads filters from a page URL so views are shareable and survive navigation to a detail row. */
export function filtersFromSearchParams(params: URLSearchParams): InvoiceFilters {
  return FILTER_KEYS.reduce<InvoiceFilters>((filters, key) => {
    const value = params.get(key);
    return value === null ? filters : { ...filters, [key]: value };
  }, EMPTY_INVOICE_FILTERS);
}

/** Only non-default values are written, so a pristine view has a clean URL. */
export function filtersToSearchParams(filters: InvoiceFilters): string {
  return buildQuery(
    Object.fromEntries(FILTER_KEYS.map((key) => [key, filters[key] === EMPTY_INVOICE_FILTERS[key] ? "" : filters[key]])),
  );
}
