// Pure review-gate helpers for the inbox (PROJECT_SPECS §6.5–§6.6). No I/O, no React.
// The API is authoritative; these mirror apps/mail/services/review.py so the UI never
// offers Approve/Send when the server would refuse.
import type { Draft, DraftSummary, Priority } from "@/lib/types";

/** §6.5 guardrail flags in spec order; any raised flag blocks approve until acknowledged. */
export const GUARDRAIL_FLAGS = [
  "promises_discount_or_waiver",
  "commits_to_date_or_delivery",
  "quotes_a_price",
  "legal_language",
  "contains_bank_details",
  "references_invoice_not_in_db",
  "amount_mismatch_with_db",
  "injection_suspected",
  "party_unresolved",
  "outside_business_scope",
  "sentiment_escalation",
] as const;

export interface AcknowledgedFlag {
  reviewer: string;
  flag: string;
  at: string;
}

/** Roles allowed to approve, reject and send (§6.6 "reviewer lacks the role"). */
const REVIEW_ROLES: readonly string[] = ["owner", "accountant", "reviewer"];

export function canReview(role: string | null | undefined): boolean {
  return role !== null && role !== undefined && REVIEW_ROLES.includes(role);
}

/** The API stores acknowledged_flags as untyped JSON; keep only well-formed entries. */
export function acknowledgedFlags(raw: unknown): AcknowledgedFlag[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null) return [];
    const { reviewer, flag, at } = entry as Record<string, unknown>;
    if (typeof flag !== "string") return [];
    return [{ reviewer: typeof reviewer === "string" ? reviewer : "", flag, at: typeof at === "string" ? at : "" }];
  });
}

/** guardrail_flags − acknowledged flags. Non-empty ⇒ no Approve/Send control may render. */
export function unacknowledgedFlags(draft: Pick<Draft | DraftSummary, "guardrail_flags" | "acknowledged_flags">): string[] {
  const acked = new Set(acknowledgedFlags(draft.acknowledged_flags).map((entry) => entry.flag));
  return (draft.guardrail_flags ?? []).filter((flag) => !acked.has(flag));
}

const APPROVABLE_STATUSES: readonly string[] = ["pending_review"];
const SENDABLE_STATUSES: readonly string[] = ["approved", "edited_approved"];

export function canApproveDraft(role: string | null | undefined, draft: Pick<Draft, "guardrail_flags" | "acknowledged_flags" | "status">): boolean {
  return canReview(role) && APPROVABLE_STATUSES.includes(draft.status) && unacknowledgedFlags(draft).length === 0;
}

export function canSendDraft(role: string | null | undefined, draft: Pick<Draft, "guardrail_flags" | "acknowledged_flags" | "status">): boolean {
  return canReview(role) && SENDABLE_STATUSES.includes(draft.status) && unacknowledgedFlags(draft).length === 0;
}

// ---- SLA countdown -------------------------------------------------------------------------------
export type SlaTone = "danger" | "warning" | "muted";
export interface SlaCountdown {
  label: string;
  tone: SlaTone;
  isBreached: boolean;
}

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const WARNING_WINDOW_MS = 4 * HOUR_MS;

function spanLabel(ms: number): string {
  if (ms >= DAY_MS) return `${Math.floor(ms / DAY_MS)}d ${Math.floor((ms % DAY_MS) / HOUR_MS)}h`;
  if (ms >= HOUR_MS) return `${Math.floor(ms / HOUR_MS)}h ${Math.floor((ms % HOUR_MS) / MINUTE_MS)}m`;
  return `${Math.max(1, Math.floor(ms / MINUTE_MS))}m`;
}

/** "2h 10m left" (muted), "<4h" (warning), "overdue by 1d 2h" (danger). Both args ISO strings. */
export function slaCountdown(slaDueAt: string | null | undefined, nowIso: string): SlaCountdown | null {
  if (!slaDueAt) return null;
  const due = Date.parse(slaDueAt);
  const now = Date.parse(nowIso);
  if (Number.isNaN(due) || Number.isNaN(now)) return null;
  const remaining = due - now;
  if (remaining <= 0) return { label: `overdue by ${spanLabel(-remaining)}`, tone: "danger", isBreached: true };
  return { label: `${spanLabel(remaining)} left`, tone: remaining < WARNING_WINDOW_MS ? "warning" : "muted", isBreached: false };
}

/** §9: semantic colour only for status — urgent/high carry a tone, the rest stay neutral. */
export function priorityTone(priority: Priority | undefined): "danger" | "warning" | "muted" {
  if (priority === "urgent") return "danger";
  if (priority === "high") return "warning";
  return "muted";
}
