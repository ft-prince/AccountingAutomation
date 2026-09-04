"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import { priorityTone, slaCountdown, type SlaTone } from "@/lib/mail-review";
import type { Intent, Priority } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<SlaTone, string> = { danger: "border-danger text-danger", warning: "border-warning text-warning", muted: "border-border text-muted" };
const CLOCK_TICK_MS = 30_000;

/** Wall clock that re-renders every 30 s so SLA countdowns stay honest. Injectable for tests. */
export function useNow(fixedNow?: string): string {
  const [now, setNow] = useState(() => fixedNow ?? new Date().toISOString());
  useEffect(() => {
    if (fixedNow) return undefined;
    const timer = setInterval(() => setNow(new Date().toISOString()), CLOCK_TICK_MS);
    return () => clearInterval(timer);
  }, [fixedNow]);
  return now;
}

export function IntentChip({ intent }: { intent: Intent | "" | undefined }) {
  if (!intent) return null;
  return (
    <Badge variant="outline" data-intent={intent} className="border-border font-normal text-muted">
      {humanize(intent)}
    </Badge>
  );
}

export function PriorityChip({ priority }: { priority: Priority | undefined }) {
  if (!priority || priority === "normal") return null;
  return (
    <Badge variant="outline" data-priority={priority} className={cn("font-medium", TONE_CLASS[priorityTone(priority)])}>
      {humanize(priority)}
    </Badge>
  );
}

export function SlaChip({ slaDueAt, now }: { slaDueAt: string | null | undefined; now: string }) {
  const countdown = slaCountdown(slaDueAt, now);
  if (!countdown) return <span className="text-xs text-muted">no SLA</span>;
  return (
    <span data-sla-tone={countdown.tone} className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs tabular-nums", TONE_CLASS[countdown.tone])}>
      {countdown.label}
    </span>
  );
}
