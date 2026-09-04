"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { buildQuery, type Paginated } from "@/lib/query";
import type { Party, PartyKind } from "@/lib/types";

export const PARTIES_KEY = "parties";
const PARTY_SEARCH_LIMIT = 20;

export interface PartyFilters {
  q?: string;
  kind?: PartyKind | "";
  includeInactive?: boolean;
  cursor?: string | null;
}

export function partiesPath(filters: PartyFilters): string {
  return `/api/parties/${buildQuery({
    q: filters.q,
    kind: filters.kind,
    include_inactive: filters.includeInactive ? 1 : undefined,
    cursor: filters.cursor ?? undefined,
  })}`;
}

export function useParties(filters: PartyFilters, enabled = true) {
  return useQuery({
    queryKey: [PARTIES_KEY, "list", filters],
    queryFn: () => api<Paginated<Party>>(partiesPath(filters)),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** Lightweight search for combo boxes; only runs once there is a query. */
export function usePartySearch(query: string) {
  return useQuery({
    queryKey: [PARTIES_KEY, "search", query],
    queryFn: async () => (await api<Paginated<Party>>(partiesPath({ q: query }))).results.slice(0, PARTY_SEARCH_LIMIT),
    enabled: query.trim().length > 0,
    staleTime: 30_000,
  });
}

export function useParty(id: string, enabled = true) {
  return useQuery({ queryKey: [PARTIES_KEY, "detail", id], queryFn: () => api<Party>(`/api/parties/${id}/`), enabled: enabled && id !== "" });
}

export type PartyInput = Partial<Omit<Party, "id" | "merged_into" | "created_at" | "updated_at">> & { legal_name: string };

export function useSaveParty() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id?: string; body: PartyInput }) =>
      input.id
        ? api<Party>(`/api/parties/${input.id}/`, { method: "PATCH", body: JSON.stringify(input.body) })
        : api<Party>("/api/parties/", { method: "POST", body: JSON.stringify(input.body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [PARTIES_KEY] }),
  });
}

export function useMergeParty() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { sourceId: string; targetId: string }) =>
      api<Party>(`/api/parties/${input.sourceId}/merge/`, { method: "POST", body: JSON.stringify({ target: input.targetId }) }),
    onSuccess: () => client.invalidateQueries(),
  });
}

export function partyDisplayName(party: Pick<Party, "legal_name" | "display_name">): string {
  return party.display_name?.trim() || party.legal_name;
}
