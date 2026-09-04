import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

export type StatusTone = "success" | "warning" | "danger" | "info" | "muted";

// §9: semantic colours are for status only. Every enum the API exposes maps onto one tone.
const TONES: Record<string, StatusTone> = {
  confirmed: "success",
  paid: "success",
  extracted: "success",
  valid: "success",
  matched: "success",
  auto: "success",
  manual: "success",
  active: "success",
  needs_review: "warning",
  partial: "warning",
  warnings: "warning",
  pending: "info",
  extracting: "info",
  uploading: "info",
  processing: "info",
  queued: "muted",
  unpaid: "info",
  proposed: "info",
  rejected: "danger",
  failed: "danger",
  overdue: "danger",
  invalid: "danger",
  error: "danger",
  duplicate: "muted",
  superseded: "muted",
  written_off: "muted",
  ignored: "muted",
  unmatched: "warning",
  revoked: "muted",
};

const TONE_CLASS: Record<StatusTone, string> = {
  success: "border-success text-success",
  warning: "border-warning text-warning",
  danger: "border-danger text-danger",
  info: "border-info text-info",
  muted: "border-border text-muted",
};

export interface StatusBadgeProps {
  status: string | null | undefined;
  tone?: StatusTone;
  label?: string;
  className?: string;
}

export function statusTone(status: string | null | undefined): StatusTone {
  return (status && TONES[status]) || "muted";
}

export function StatusBadge({ status, tone, label, className }: StatusBadgeProps) {
  const resolved = tone ?? statusTone(status);
  return (
    <Badge variant="outline" data-status={status ?? ""} className={cn("font-medium", TONE_CLASS[resolved], className)}>
      {label ?? humanize(status)}
    </Badge>
  );
}
