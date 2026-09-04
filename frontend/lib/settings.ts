"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ME_QUERY_KEY, type MeOrg } from "@/lib/auth";
import type { Paginated } from "@/lib/query";
import type { ApiKey, GstinProfile, MemberRole, Membership } from "@/lib/types";

export const SETTINGS_KEY = "settings";

// ---- Organisation -------------------------------------------------------------------------------
export type OrgInput = Pick<MeOrg, "name" | "legal_name" | "pan" | "brand_display_name">;

export function useOrg() {
  return useQuery({ queryKey: [SETTINGS_KEY, "org"], queryFn: () => api<MeOrg>("/api/orgs/current") });
}

export function useUpdateOrg() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<OrgInput>) => api<MeOrg>("/api/orgs/current", { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [SETTINGS_KEY, "org"] });
      void client.invalidateQueries({ queryKey: ME_QUERY_KEY });
    },
  });
}

// ---- GSTINs -------------------------------------------------------------------------------------
export type GstinInput = Pick<GstinProfile, "gstin" | "state_code" | "trade_name" | "registration_type" | "is_default" | "valid_from" | "valid_to">;

export function useGstins() {
  return useQuery({ queryKey: [SETTINGS_KEY, "gstins"], queryFn: async () => (await api<Paginated<GstinProfile>>("/api/gstins/")).results });
}

export function useSaveGstin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id?: string; body: Partial<GstinInput> }) =>
      input.id
        ? api<GstinProfile>(`/api/gstins/${input.id}/`, { method: "PATCH", body: JSON.stringify(input.body) })
        : api<GstinProfile>("/api/gstins/", { method: "POST", body: JSON.stringify(input.body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [SETTINGS_KEY, "gstins"] }),
  });
}

// ---- Members ------------------------------------------------------------------------------------
export function useMembers() {
  return useQuery({ queryKey: [SETTINGS_KEY, "members"], queryFn: async () => (await api<Paginated<Membership>>("/api/members/")).results });
}

export function useInviteMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: MemberRole }) => api<Membership>("/api/members/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [SETTINGS_KEY, "members"] }),
  });
}

export function useUpdateMemberRole() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; role: MemberRole }) =>
      api<Membership>(`/api/members/${input.id}/`, { method: "PATCH", body: JSON.stringify({ role: input.role }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [SETTINGS_KEY, "members"] }),
  });
}

export function useRemoveMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/members/${id}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [SETTINGS_KEY, "members"] }),
  });
}

// ---- Extraction toggles -------------------------------------------------------------------------
export interface ExtractionSettings {
  auto_confirm: boolean;
  extraction_enabled: boolean;
  send_page_images_for_scans: boolean;
}

export function useExtractionSettings() {
  return useQuery({ queryKey: [SETTINGS_KEY, "extraction"], queryFn: () => api<ExtractionSettings>("/api/settings") });
}

export function useUpdateExtractionSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ExtractionSettings) => api<ExtractionSettings>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (data) => client.setQueryData([SETTINGS_KEY, "extraction"], data),
  });
}

// ---- API keys -----------------------------------------------------------------------------------
export type CreatedApiKey = ApiKey & { key: string };

export function useApiKeys() {
  return useQuery({ queryKey: [SETTINGS_KEY, "api-keys"], queryFn: async () => (await api<Paginated<ApiKey>>("/api/api-keys/")).results });
}

export function useCreateApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api<CreatedApiKey>("/api/api-keys/", { method: "POST", body: JSON.stringify({ name }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [SETTINGS_KEY, "api-keys"] }),
  });
}

export function useRevokeApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/api-keys/${id}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [SETTINGS_KEY, "api-keys"] }),
  });
}
