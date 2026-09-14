"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/query";
import type { Notification } from "@/lib/types";

export const NOTIFICATIONS_KEY = "notifications";
const POLL_MS = 60_000;

/** Open (not dismissed) notifications, newest first. Polled: backups and mailbox errors raise them. */
export function useNotifications() {
  return useQuery({
    queryKey: [NOTIFICATIONS_KEY],
    queryFn: async () => (await api<Paginated<Notification>>("/api/notifications/")).results,
    refetchInterval: POLL_MS,
  });
}

export function useNotificationAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; action: "read" | "dismiss" }) =>
      api<Notification>(`/api/notifications/${input.id}/${input.action}/`, { method: "POST", body: "{}" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [NOTIFICATIONS_KEY] }),
  });
}
