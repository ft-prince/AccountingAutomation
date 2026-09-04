"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/query";
import type { FixedLine, ForecastPoint, ForecastRun, RecurringPattern, Scenario } from "@/lib/types";

export const FORECAST_KEY = "forecast";
const FORECAST_STALE_MS = 60_000;

// Read-only computed views in apps/forecasting/views.py return plain dicts (no OpenAPI body);
// these mirror services/drivers.py and services/analytics.py field-for-field.
export type DriverSource = "invoice" | "recurring" | "fixed_line" | "statutory";
export interface Driver {
  direction: "inflow" | "outflow";
  label: string;
  amount: string;
  date: string;
  source: DriverSource;
  party: string | null;
}

export type RiskBand = "low" | "watch" | "high";
export interface CustomerRisk {
  party: string;
  party_name: string;
  score: string;
  band: RiskBand;
  drivers: string[];
  mean_days: string;
  std_days: string;
  trend_days: string;
  share_overdue: string;
  utilisation: string | null;
}

export type AnomalyKind = "amount" | "gap" | "new_vendor" | "duplicate";
export interface Anomaly {
  invoice: string;
  kind: AnomalyKind;
  party: string | null;
  party_name: string;
  category: string | null;
  category_name: string;
  z: string | null;
  detail: string;
  related_invoice: string | null;
}
export interface AnomaliesReport {
  as_of: string;
  window_days: number;
  expenses: Anomaly[];
  duplicates: Anomaly[];
  concentration: {
    top1_party: string | null;
    top1_party_name: string;
    top1_share: string;
    top3_parties: string[];
    top3_share: string;
    is_top1_flagged: boolean;
    is_top3_flagged: boolean;
  };
}

export interface BacktestReport {
  run: string;
  as_of: string;
  history_days: number;
  insufficient_history: boolean;
  mape: string | null;
  coverage: string | null;
  n_origins: number | null;
  is_calibrated: boolean | null;
  checkpoints: unknown[];
}

export interface NarrativeResponse {
  narrative: string | null;
  generated: boolean;
  label: string;
}

export interface ScenarioRunResult {
  scenario: string;
  base_run: string | null;
  as_of: string;
  horizon_days: number;
  n_paths: number;
  seed: number;
  runway_date: string | null;
  points: ForecastPoint[];
}

/** §8.4 override kinds, exactly as apps/forecasting/domain/scenarios.py accepts them. */
export type ScenarioOverride =
  | { kind: "delay_customer"; party: string; days: number }
  | { kind: "lose_customer"; party: string }
  | { kind: "delay_vendor"; party: string; days: number }
  | { kind: "add_fixed_line"; name: string; amount: string; cadence: FixedLine["cadence"]; next_date: string; direction: FixedLine["direction"] }
  | { kind: "remove_fixed_line"; name: string }
  | { kind: "collection_policy_shift"; days: number }
  | { kind: "new_hire"; amount: string; start: string };

// ---- Runs ------------------------------------------------------------------------------------------
export function useLatestForecast(enabled = true) {
  return useQuery({
    queryKey: [FORECAST_KEY, "latest"],
    queryFn: () => api<ForecastRun>("/api/forecast/latest"),
    staleTime: FORECAST_STALE_MS,
    retry: false,
    enabled,
  });
}

export function useRunForecast() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (horizonDays: number) => api<ForecastRun>("/api/forecast/run", { method: "POST", body: JSON.stringify({ horizon_days: horizonDays }) }),
    onSuccess: (run) => {
      client.setQueryData([FORECAST_KEY, "latest"], run);
      void client.invalidateQueries({ queryKey: [FORECAST_KEY] });
    },
  });
}

export function useGenerateNarrative() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api<NarrativeResponse>(`/api/forecast/runs/${runId}/narrative`, { method: "POST", body: "{}" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [FORECAST_KEY, "latest"] }),
  });
}

export function useBacktest(enabled = true) {
  return useQuery({ queryKey: [FORECAST_KEY, "backtest"], queryFn: () => api<BacktestReport>("/api/forecast/backtest"), retry: false, enabled });
}

export function useDrivers(enabled = true) {
  return useQuery({ queryKey: [FORECAST_KEY, "drivers"], queryFn: () => api<Driver[]>("/api/forecast/drivers"), staleTime: FORECAST_STALE_MS, enabled });
}

export function useCustomerRisk(enabled = true) {
  return useQuery({ queryKey: [FORECAST_KEY, "risk"], queryFn: () => api<CustomerRisk[]>("/api/forecast/risk/customers"), staleTime: FORECAST_STALE_MS, enabled });
}

export function useAnomalies(enabled = true) {
  return useQuery({ queryKey: [FORECAST_KEY, "anomalies"], queryFn: () => api<AnomaliesReport>("/api/forecast/anomalies"), staleTime: FORECAST_STALE_MS, enabled });
}

// ---- Scenarios -----------------------------------------------------------------------------------
export function useScenarios() {
  return useQuery({ queryKey: [FORECAST_KEY, "scenarios"], queryFn: async () => (await api<Paginated<Scenario>>("/api/forecast/scenarios/")).results });
}

export function useCreateScenario() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; overrides: ScenarioOverride[] }) => api<Scenario>("/api/forecast/scenarios/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [FORECAST_KEY, "scenarios"] }),
  });
}

export function useRunScenario() {
  return useMutation({ mutationFn: (id: string) => api<ScenarioRunResult>(`/api/forecast/scenarios/${id}/run`, { method: "POST", body: "{}" }) });
}

// ---- Recurring patterns ----------------------------------------------------------------------------
export function useRecurringPatterns() {
  return useQuery({ queryKey: [FORECAST_KEY, "recurring"], queryFn: async () => (await api<Paginated<RecurringPattern>>("/api/forecast/recurring/")).results });
}

export function useConfirmRecurring() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; user_confirmed: boolean }) =>
      api<RecurringPattern>(`/api/forecast/recurring/${input.id}/`, { method: "PATCH", body: JSON.stringify({ user_confirmed: input.user_confirmed }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [FORECAST_KEY, "recurring"] }),
  });
}

// ---- Fixed lines -----------------------------------------------------------------------------------
export type FixedLineInput = Pick<FixedLine, "name" | "amount" | "cadence" | "next_date" | "direction" | "is_active">;

export function useFixedLines() {
  return useQuery({ queryKey: [FORECAST_KEY, "fixed-lines"], queryFn: async () => (await api<Paginated<FixedLine>>("/api/forecast/fixed-lines/")).results });
}

export function useCreateFixedLine() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: FixedLineInput) => api<FixedLine>("/api/forecast/fixed-lines/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [FORECAST_KEY, "fixed-lines"] }),
  });
}
