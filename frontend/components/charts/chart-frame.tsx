import { BarChart3 } from "lucide-react";
import type { ReactNode } from "react";
import { BasisBadge } from "@/components/primitives/basis-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ICON_STROKE } from "@/lib/constants";
import type { ReportMeta } from "@/lib/reports";
import { cn } from "@/lib/utils";

export interface ChartFrameProps {
  title: string;
  /** Report meta: every chart states its period and pending count (§7.4). */
  meta: ReportMeta | undefined;
  periodLabel?: string;
  isPending?: boolean;
  error?: unknown;
  isEmpty?: boolean;
  emptyText?: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

export const CHART_HEIGHT = 240;

export function ChartFrame({ title, meta, periodLabel, isPending = false, error, isEmpty = false, emptyText = "Nothing in this period", actions, className, children }: ChartFrameProps) {
  const period = periodLabel ?? (meta ? `${meta.period.from} → ${meta.period.to}` : "");
  return (
    <section aria-label={title} className={cn("flex min-w-0 flex-col rounded-card border border-border bg-surface p-5", className)}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="mt-0.5 text-xs text-muted tabular-nums">{period || "—"}</p>
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {meta && <BasisBadge basis={meta.basis} pendingCount={meta.pending_count} />}
        </div>
      </header>
      <div className="mt-4 min-h-[240px] min-w-0 flex-1">
        {isPending ? (
          <Skeleton className="h-[240px] w-full" aria-busy />
        ) : error ? (
          <p role="alert" className="text-sm text-danger">
            {error instanceof Error ? error.message : "Could not load"}
          </p>
        ) : isEmpty ? (
          <div className="flex h-[240px] flex-col items-center justify-center text-center">
            <BarChart3 size={22} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
            <p className="mt-2 text-sm text-muted">{emptyText}</p>
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}
