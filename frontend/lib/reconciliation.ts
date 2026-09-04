"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Big from "big.js";
import { api } from "@/lib/api";
import { orZero } from "@/lib/money";
import type { ImsAction, MatchType, ReconBatch, ReconMatch, ReconRecord } from "@/lib/types";

export const RECON_KEY = "reconciliation";

/** Match rows as GET /api/reconciliation/{batch} returns them: MatchSerializer + a running total. */
export interface GroupedMatch extends ReconMatch {
  running_itc_at_risk: string;
}

export const MATCH_TYPES: readonly MatchType[] = ["exact", "fuzzy", "value_mismatch", "missing_in_books", "missing_in_2b"];

export interface BatchDetail {
  batch: ReconBatch;
  counts: Record<string, number>;
  itc_at_risk: string;
  records: ReconRecord[];
  matches: Record<MatchType, GroupedMatch[]>;
}

export interface GroupSummary {
  type: MatchType;
  count: number;
  /** Sum of at_risk for the group (exact decimal). */
  atRisk: string;
  /** Running ITC-at-risk after this group, in MATCH_TYPES order. */
  runningAtRisk: string;
}

/** Pure: per-type counts, group totals and the running total the UI shows beside each column. */
export function groupSummaries(matches: Partial<Record<MatchType, readonly GroupedMatch[]>>): GroupSummary[] {
  let running = new Big(0);
  return MATCH_TYPES.map((type) => {
    const rows = matches[type] ?? [];
    const atRisk = rows.reduce((total, row) => total.plus(new Big(orZero(row.at_risk))), new Big(0));
    running = running.plus(atRisk);
    return { type, count: rows.length, atRisk: atRisk.toFixed(2), runningAtRisk: running.toFixed(2) };
  });
}

export function totalAtRisk(matches: Partial<Record<MatchType, readonly GroupedMatch[]>>): string {
  const summaries = groupSummaries(matches);
  return summaries[summaries.length - 1]?.runningAtRisk ?? "0.00";
}

// ---- Hooks ------------------------------------------------------------------------------------------
export function useBatches() {
  return useQuery({ queryKey: [RECON_KEY, "batches"], queryFn: async () => (await api<{ results: ReconBatch[] }>("/api/reconciliation/")).results });
}

export function useBatchDetail(batchId: string | null) {
  return useQuery({ queryKey: [RECON_KEY, "batch", batchId], queryFn: () => api<BatchDetail>(`/api/reconciliation/${batchId}/`), enabled: Boolean(batchId) });
}

export function useImport2b() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; period: string }) => {
      const form = new FormData();
      form.append("file", input.file);
      form.append("period", input.period);
      return api<ReconBatch>("/api/reconciliation/import-2b/", { method: "POST", body: form });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [RECON_KEY, "batches"] }),
  });
}

export function useRunReconciliation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => api<ReconBatch>(`/api/reconciliation/run/?batch=${encodeURIComponent(batchId)}`, { method: "POST", body: "{}" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [RECON_KEY] }),
  });
}

export function useImsAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { recordId: string; action: ImsAction; note?: string }) =>
      api<ReconRecord>(`/api/reconciliation/records/${input.recordId}/ims/`, { method: "POST", body: JSON.stringify({ action: input.action, note: input.note ?? "" }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [RECON_KEY, "batch"] }),
  });
}

export interface MatchPatch {
  match_type?: MatchType;
  note?: string;
  invoice?: string | null;
}

export function usePatchMatch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { matchId: string; body: MatchPatch }) => api<ReconMatch>(`/api/reconciliation/matches/${input.matchId}/`, { method: "PATCH", body: JSON.stringify(input.body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [RECON_KEY, "batch"] }),
  });
}
