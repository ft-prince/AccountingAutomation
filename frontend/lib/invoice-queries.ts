"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NewInvoiceBody } from "@/lib/invoice-draft";
import { invoicesListPath, type InvoiceFilters, type InvoiceQueryOptions } from "@/lib/invoice-filters";
import type { Paginated } from "@/lib/query";
import type { InvoiceDetail, InvoiceList } from "@/lib/types";

export const INVOICES_KEY = "invoices";

export function useInvoiceList(filters: InvoiceFilters, options: InvoiceQueryOptions = {}) {
  return useQuery({
    queryKey: [INVOICES_KEY, "list", filters, options],
    queryFn: () => api<Paginated<InvoiceList>>(invoicesListPath(filters, options)),
    placeholderData: keepPreviousData,
  });
}

export function useInvoiceDetail(id: string) {
  return useQuery({ queryKey: [INVOICES_KEY, "detail", id], queryFn: () => api<InvoiceDetail>(`/api/invoices/${id}/`) });
}

// ---- Manual entry and CSV import (§11 /invoices) -------------------------------------------------

/** GET → text/csv attachment with the exact column set the importer expects. */
export const INVOICE_IMPORT_TEMPLATE_URL = "/api/invoices/import-template/";

export interface ImportedInvoice {
  invoice_number: string;
  id: string;
  total: string;
}

export interface ImportRowError {
  invoice_number: string;
  row: number;
  error: string;
}

/** 207 body from POST /api/invoices/import/ — partial success is the normal case. */
export interface InvoiceImportResult {
  created: ImportedInvoice[];
  errors: ImportRowError[];
  invoices: number;
  failed: number;
}

export function useCreateInvoice() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewInvoiceBody) => api<InvoiceDetail>("/api/invoices/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [INVOICES_KEY] }),
  });
}

export function useImportInvoices() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<InvoiceImportResult>("/api/invoices/import/", { method: "POST", body: form });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [INVOICES_KEY] }),
  });
}

export type BulkConfirmResponse = { results: Record<string, string> };

export function useBulkConfirm() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { ids: string[]; force?: boolean }) =>
      api<BulkConfirmResponse>("/api/invoices/bulk-confirm/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [INVOICES_KEY] }),
  });
}

export function useMarkDuplicate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(ids.map((id) => api<unknown>(`/api/invoices/${id}/mark-duplicate/`, { method: "POST" })));
      return { failed: results.filter((result) => result.status === "rejected").length, total: ids.length };
    },
    onSettled: () => client.invalidateQueries({ queryKey: [INVOICES_KEY] }),
  });
}
