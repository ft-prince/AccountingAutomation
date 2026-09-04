"use client";

// TanStack Query hooks for the /review screen. Types come from the generated OpenAPI schema.
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { components } from "@/lib/types.gen";

export type InvoiceDetail = components["schemas"]["InvoiceDetail"];
export type InvoiceList = components["schemas"]["InvoiceList"];
export type InvoiceLine = components["schemas"]["Line"];
export type InvoiceLineWrite = components["schemas"]["LineWrite"];
export type InvoicePatch = components["schemas"]["PatchedInvoicePatch"];
export type ValidationIssue = components["schemas"]["Issue"];
export type Party = components["schemas"]["Party"];
export type SupplyType = components["schemas"]["SupplyTypeEnum"];

export interface ReviewQueuePage {
  results: InvoiceList[];
  next: string | null;
  previous: string | null;
}

export interface SignedFile {
  url: string;
  expires_in: number;
}

export interface AgingRow {
  party: string;
  name: string;
  "0-30": string;
  "31-60": string;
  "61-90": string;
  "90+": string;
  total: string;
}

export interface AgingReport {
  rows: AgingRow[];
}

export const CONFIRM_ROLES: readonly string[] = ["owner", "accountant"];

export const invoiceKeys = {
  all: ["invoices"] as const,
  queue: () => ["invoices", "review-queue"] as const,
  detail: (id: string) => ["invoices", "detail", id] as const,
  file: (documentId: string) => ["documents", "file", documentId] as const,
  party: (id: string) => ["parties", id] as const,
  aging: (kind: "ar" | "ap") => ["reports", `${kind}-aging`] as const,
};

const QUEUE_PATH = "/api/invoices/review-queue/";
const SIGNED_URL_SAFETY_MS = 15_000;
const MS_PER_SECOND = 1000;
const AGING_STALE_MS = 5 * 60_000;

/** DRF emits absolute `next` URLs on the Django host; keep only path + query so the request stays same-origin. */
export function sameOriginPath(url: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url, "http://localhost");
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return null;
  }
}

export function useReviewQueue() {
  return useInfiniteQuery({
    queryKey: invoiceKeys.queue(),
    queryFn: ({ pageParam }) => api<ReviewQueuePage>(pageParam ?? QUEUE_PATH),
    initialPageParam: QUEUE_PATH as string | null,
    getNextPageParam: (page) => sameOriginPath(page.next),
    staleTime: Infinity, // queue order only changes through this screen's own actions; invalidated when the screen unmounts
  });
}

function fetchInvoice(id: string): Promise<InvoiceDetail> {
  return api<InvoiceDetail>(`/api/invoices/${id}/`);
}

export function useInvoice(id: string | null) {
  return useQuery({
    queryKey: invoiceKeys.detail(id ?? ""),
    queryFn: () => fetchInvoice(id ?? ""),
    enabled: id !== null,
  });
}

/** Warms the next invoice so advancing is instant (the 8-second-per-invoice budget). */
export function prefetchInvoice(client: QueryClient, id: string): Promise<void> {
  return client.prefetchQuery({ queryKey: invoiceKeys.detail(id), queryFn: () => fetchInvoice(id) });
}

/** Signed URL for the PDF (5 min). Refetched shortly before it expires. */
export function useDocumentFile(documentId: string | null) {
  return useQuery({
    queryKey: invoiceKeys.file(documentId ?? ""),
    queryFn: () => api<SignedFile>(`/api/documents/${documentId}/file/`),
    enabled: documentId !== null,
    staleTime: (query) => expiryMs(query.state.data),
    refetchInterval: (query) => expiryMs(query.state.data) || false,
  });
}

function expiryMs(file: SignedFile | undefined): number {
  if (!file) return 0;
  return Math.max(file.expires_in * MS_PER_SECOND - SIGNED_URL_SAFETY_MS, MS_PER_SECOND);
}

export function useParty(id: string | null) {
  return useQuery({
    queryKey: invoiceKeys.party(id ?? ""),
    queryFn: () => api<Party>(`/api/parties/${id}/`),
    enabled: id !== null,
  });
}

/** Inward invoices are payables (ap-aging); outward are receivables (ar-aging). */
export function useAging(kind: "ar" | "ap") {
  return useQuery({
    queryKey: invoiceKeys.aging(kind),
    queryFn: () => api<AgingReport>(`/api/reports/${kind}-aging`),
    staleTime: AGING_STALE_MS,
  });
}

function useInvoiceMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<InvoiceDetail>,
  invoiceIdOf: (variables: TVariables) => string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (detail, variables) => {
      client.setQueryData(invoiceKeys.detail(invoiceIdOf(variables)), detail);
    },
  });
}

export function useUpdateInvoice() {
  return useInvoiceMutation(
    ({ id, patch }: { id: string; patch: InvoicePatch }) =>
      api<InvoiceDetail>(`/api/invoices/${id}/`, { method: "PATCH", body: JSON.stringify(patch) }),
    ({ id }) => id,
  );
}

export function useConfirmInvoice() {
  return useInvoiceMutation(
    ({ id, force }: { id: string; force?: boolean }) =>
      api<InvoiceDetail>(`/api/invoices/${id}/confirm/`, { method: "POST", body: JSON.stringify({ force: force ?? false }) }),
    ({ id }) => id,
  );
}

export function useRejectInvoice() {
  return useInvoiceMutation(
    ({ id, reason }: { id: string; reason: string }) =>
      api<InvoiceDetail>(`/api/invoices/${id}/reject/`, { method: "POST", body: JSON.stringify({ reason }) }),
    ({ id }) => id,
  );
}

export function useMarkDuplicate() {
  return useInvoiceMutation(
    ({ id, duplicateOf }: { id: string; duplicateOf?: string }) =>
      api<InvoiceDetail>(`/api/invoices/${id}/mark-duplicate/`, {
        method: "POST",
        body: JSON.stringify(duplicateOf ? { duplicate_of: duplicateOf } : {}),
      }),
    ({ id }) => id,
  );
}

export function useResolveIssue() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ invoiceId, issueId, note }: { invoiceId: string; issueId: string; note: string }) =>
      api<ValidationIssue | InvoiceDetail>(`/api/invoices/${invoiceId}/issues/${issueId}/resolve/`, {
        method: "POST",
        body: JSON.stringify({ note }),
      }),
    onSuccess: (_data, { invoiceId }) => client.invalidateQueries({ queryKey: invoiceKeys.detail(invoiceId) }),
  });
}

/** Issues the server attached to a 400 on confirm (RFC 7807 errors.issues). */
export function issuesFromProblem(errors: Record<string, unknown> | undefined): ValidationIssue[] {
  const issues = errors?.issues;
  return Array.isArray(issues) ? (issues as ValidationIssue[]) : [];
}
