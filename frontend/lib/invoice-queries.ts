"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
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
