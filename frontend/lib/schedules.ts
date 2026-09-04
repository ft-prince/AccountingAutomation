"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/query";
import type { ReportSchedule } from "@/lib/types";

export const SCHEDULES_KEY = ["reports", "schedules"] as const;

export type ScheduleInput = Pick<ReportSchedule, "report" | "params" | "cadence" | "recipients" | "format">;

/** §7.3 scheduled reports: fixed content, no LLM text; the only non-human-approved outbound mail. */
export function useReportSchedules() {
  return useQuery({ queryKey: SCHEDULES_KEY, queryFn: async () => (await api<Paginated<ReportSchedule>>("/api/reports/schedules/")).results });
}

export function useCreateReportSchedule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ScheduleInput) => api<ReportSchedule>("/api/reports/schedules/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: SCHEDULES_KEY }),
  });
}
