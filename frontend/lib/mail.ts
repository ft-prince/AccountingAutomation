"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { buildQuery, type Paginated } from "@/lib/query";
import type { Draft, DraftSummary, Intent, MailProvider, Mailbox, ReplyTemplate, StyleGuide, ThreadDetail, ThreadList, ThreadStatus } from "@/lib/types";

export const MAIL_KEY = "mail";
const THREADS_STALE_MS = 15_000;

// Responses without an OpenAPI body (plain Response(...) in apps/mail/views.py); mirrored field-for-field.
export interface ReviewQueueItem extends DraftSummary {
  thread: string;
  body_text: string;
}

export interface MailMetrics {
  time_to_first_draft_seconds: string | number | null;
  review_time_seconds: string | number | null;
  mean_edit_distance: string | number | null;
  approval_rate_by_intent: Record<string, { approved: number; reviewed: number; rate: string | number | null }>;
  flags_per_100_drafts?: string | number | null;
  replies_per_day: { date: string; count: number }[];
}

export interface ConnectResponse {
  authorization_url: string;
  provider: MailProvider;
}

// ---- Mailboxes ------------------------------------------------------------------------------------
export function useMailboxes() {
  return useQuery({ queryKey: [MAIL_KEY, "mailboxes"], queryFn: async () => (await api<Paginated<Mailbox>>("/api/mail/mailboxes/")).results });
}

export function useConnectMailbox() {
  return useMutation({ mutationFn: (provider: MailProvider) => api<ConnectResponse>(`/api/mail/connect/${provider}`, { method: "POST", body: "{}" }) });
}

export function useGrantSendScope() {
  return useMutation({ mutationFn: (id: string) => api<ConnectResponse>(`/api/mail/mailboxes/${id}/grant-send-scope/`, { method: "POST", body: "{}" }) });
}

export function useRevokeMailbox() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Mailbox>(`/api/mail/mailboxes/${id}/revoke/`, { method: "POST", body: "{}" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [MAIL_KEY, "mailboxes"] }),
  });
}

// ---- Threads ---------------------------------------------------------------------------------------
export interface ThreadFilters {
  status?: ThreadStatus | "";
  intent?: Intent | "";
  party?: string;
}

export function useThreads(filters: ThreadFilters, enabled = true) {
  return useQuery({
    queryKey: [MAIL_KEY, "threads", filters],
    queryFn: () => api<Paginated<ThreadList>>(`/api/mail/threads/${buildQuery({ status: filters.status, intent: filters.intent, party: filters.party })}`),
    staleTime: THREADS_STALE_MS,
    enabled,
  });
}

export function useThread(id: string) {
  return useQuery({ queryKey: [MAIL_KEY, "thread", id], queryFn: () => api<ThreadDetail>(`/api/mail/threads/${id}/`) });
}

type ThreadAction = { kind: "ignore" } | { kind: "close" } | { kind: "snooze"; until: string };

export function useThreadAction(threadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: ThreadAction) =>
      api<ThreadDetail>(`/api/mail/threads/${threadId}/${action.kind}/`, { method: "POST", body: JSON.stringify(action.kind === "snooze" ? { until: action.until } : {}) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [MAIL_KEY] }),
  });
}

/** POST /threads/{id}/draft — generate or regenerate; every call is a new draft version (§6.6). */
export function useGenerateDraft(threadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (instruction?: string) => api<Draft>(`/api/mail/threads/${threadId}/draft/`, { method: "POST", body: JSON.stringify(instruction ? { instruction } : {}) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [MAIL_KEY] }),
  });
}

// ---- Drafts ----------------------------------------------------------------------------------------
export function useDraft(id: string | null | undefined) {
  return useQuery({ queryKey: [MAIL_KEY, "draft", id], queryFn: () => api<Draft>(`/api/mail/drafts/${id}/`), enabled: Boolean(id) });
}

export type DraftAction =
  | { kind: "edit"; body_text: string }
  | { kind: "acknowledge-flag"; flag: string }
  | { kind: "approve" }
  | { kind: "reject"; reason: string }
  | { kind: "send" };

function draftRequest(id: string, action: DraftAction): Promise<Draft> {
  switch (action.kind) {
    case "edit":
      return api<Draft>(`/api/mail/drafts/${id}/`, { method: "PATCH", body: JSON.stringify({ body_text: action.body_text }) });
    case "acknowledge-flag":
      return api<Draft>(`/api/mail/drafts/${id}/acknowledge-flag/`, { method: "POST", body: JSON.stringify({ flag: action.flag }) });
    case "reject":
      return api<Draft>(`/api/mail/drafts/${id}/reject/`, { method: "POST", body: JSON.stringify({ reason: action.reason }) });
    case "approve":
    case "send":
      return api<Draft>(`/api/mail/drafts/${id}/${action.kind}/`, { method: "POST", body: "{}" });
  }
}

export function useDraftAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: DraftAction) => draftRequest(id, action),
    onSuccess: (draft) => {
      client.setQueryData([MAIL_KEY, "draft", id], draft);
      void client.invalidateQueries({ queryKey: [MAIL_KEY, "thread"] });
      void client.invalidateQueries({ queryKey: [MAIL_KEY, "review-queue"] });
    },
  });
}

export function useReviewQueue() {
  return useQuery({ queryKey: [MAIL_KEY, "review-queue"], queryFn: () => api<ReviewQueueItem[]>("/api/mail/review-queue"), staleTime: THREADS_STALE_MS });
}

export function useMailMetrics() {
  return useQuery({ queryKey: [MAIL_KEY, "metrics"], queryFn: () => api<MailMetrics>("/api/mail/metrics") });
}

// ---- Style guide & templates ----------------------------------------------------------------------
export function useStyleGuide() {
  return useQuery({ queryKey: [MAIL_KEY, "style-guide"], queryFn: () => api<StyleGuide>("/api/mail/style-guide") });
}

export function useSaveStyleGuide() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Omit<StyleGuide, "updated_at">) => api<StyleGuide>("/api/mail/style-guide", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (guide) => client.setQueryData([MAIL_KEY, "style-guide"], guide),
  });
}

export function useTemplates() {
  return useQuery({ queryKey: [MAIL_KEY, "templates"], queryFn: async () => (await api<Paginated<ReplyTemplate>>("/api/mail/templates/")).results });
}

export function useCreateTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Pick<ReplyTemplate, "intent" | "name" | "body">) => api<ReplyTemplate>("/api/mail/templates/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [MAIL_KEY, "templates"] }),
  });
}
