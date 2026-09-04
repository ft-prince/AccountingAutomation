"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/query";
import type { Category } from "@/lib/types";

export const CATEGORIES_KEY = "categories";

export function useCategories() {
  return useQuery({
    queryKey: [CATEGORIES_KEY],
    queryFn: async () => (await api<Paginated<Category>>("/api/categories/?page_size=200")).results,
    staleTime: 5 * 60_000,
  });
}

export type CategoryInput = Pick<Category, "name" | "parent" | "itc_eligible" | "section_17_5_ref" | "tally_ledger_name" | "is_recurring_hint">;

export function useSaveCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id?: string; body: Partial<CategoryInput> }) =>
      input.id
        ? api<Category>(`/api/categories/${input.id}/`, { method: "PATCH", body: JSON.stringify(input.body) })
        : api<Category>("/api/categories/", { method: "POST", body: JSON.stringify(input.body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [CATEGORIES_KEY] }),
  });
}

export function useDeleteCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/categories/${id}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [CATEGORIES_KEY] }),
  });
}
