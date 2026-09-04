"use client";

import type { TooltipContentProps } from "recharts";
import { abbreviateINR, formatINR } from "@/lib/money";

export interface MoneyTooltipProps extends Pick<TooltipContentProps, "active" | "payload" | "label"> {
  /** Series dataKey → key on the row holding the original decimal string ("revenue" → "revenueText"). */
  textKeys: Record<string, string>;
}

/** Formats from the row's decimal strings; the numeric geometry value is never formatted. */
export function MoneyTooltip({ active, payload, label, textKeys }: MoneyTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const row = (payload[0]?.payload ?? {}) as Record<string, unknown>;
  return (
    <div className="rounded-card border border-border bg-surface px-3 py-2 text-xs">
      {label !== undefined && <p className="mb-1 font-medium">{String(label)}</p>}
      {payload.map((entry) => {
        const key = String(entry.dataKey ?? entry.name ?? "");
        const text = row[textKeys[key] ?? ""];
        return (
          <p key={key} className="flex items-center gap-2 tabular-nums">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: entry.color ?? entry.fill }} aria-hidden />
            <span className="text-muted">{String(entry.name ?? key)}</span>
            <span className="ml-auto pl-4 font-medium">{typeof text === "string" ? formatINR(text) : "—"}</span>
          </p>
        );
      })}
    </div>
  );
}

/** Axis ticks: Recharts hands a number; it is stringified before the ₹ formatter sees it (§9). */
export function moneyTick(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? abbreviateINR(String(value)) : "";
}
