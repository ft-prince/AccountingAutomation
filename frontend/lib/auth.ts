"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, ApiError, ensureCsrfCookie } from "@/lib/api";
import { ROUTES } from "@/lib/routes";

// TODO(backend): MeView carries no @extend_schema, so openapi-typescript emits no
// response body for GET /api/auth/me and this shape cannot be generated yet.
// It mirrors apps/accounts/serializers.py::MeSerializer exactly; swap for
// components["schemas"]["Me"] from lib/types.gen.ts once the view is annotated.
export interface MeOrg {
  id: string;
  name: string;
  legal_name: string;
  pan: string;
  aato_bracket: string;
  brand_display_name: string;
  settings: Record<string, unknown>;
  created_at: string;
}

export interface Me {
  user: { id: string; email: string; full_name: string };
  org: MeOrg | null;
  role: string | null;
  orgs: { id: string; name: string; role: string }[];
}

export const ME_QUERY_KEY = ["auth", "me"] as const;
const ME_STALE_MS = 60_000;

export function useUser() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: () => api<Me>("/api/auth/me"),
    staleTime: ME_STALE_MS,
    retry: (count, error) => !(error instanceof ApiError && error.isUnauthenticated) && count < 1,
  });
}

export function useLogin() {
  const client = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      await ensureCsrfCookie();
      return api<{ ok: true }>("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) });
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ME_QUERY_KEY });
      router.replace(ROUTES.dashboard);
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: () => api<void>("/api/auth/logout", { method: "POST" }),
    onSuccess: () => {
      client.clear();
      router.replace(ROUTES.login);
    },
  });
}

export function useSwitchOrg() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (orgId: string) =>
      api<{ ok: true }>("/api/auth/me", { method: "POST", body: JSON.stringify({ org_id: orgId }) }),
    onSuccess: () => client.invalidateQueries(),
  });
}
