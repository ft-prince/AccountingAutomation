"use client";

import { AlertTriangle, Copy, PieChart, UserPlus } from "lucide-react";
import Link from "next/link";
import { QueryState } from "@/components/primitives/query-state";
import { ICON_STROKE } from "@/lib/constants";
import type { AnomaliesReport, Anomaly, AnomalyKind } from "@/lib/forecast";

const KIND_ICON: Record<AnomalyKind, typeof AlertTriangle> = { amount: AlertTriangle, gap: AlertTriangle, new_vendor: UserPlus, duplicate: Copy };

function AnomalyRow({ anomaly }: { anomaly: Anomaly }) {
  const Icon = KIND_ICON[anomaly.kind] ?? AlertTriangle;
  return (
    <li className="py-2.5">
      <Link href={`/invoices/${anomaly.invoice}`} className="flex items-start gap-3 hover:text-accent">
        <Icon size={16} strokeWidth={ICON_STROKE} className="mt-0.5 shrink-0 text-warning" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm">{anomaly.kind.replace(/_/g, " ")} · {anomaly.party_name || "unknown party"}{anomaly.category_name && ` · ${anomaly.category_name}`}</span>
          <span className="block text-xs text-muted">{anomaly.detail}{anomaly.z && ` · z ${anomaly.z}`}</span>
        </span>
      </Link>
    </li>
  );
}

/** §8.5 expense anomalies, duplicates and revenue concentration. */
export function AnomaliesFeed({ report, isPending, error, onRetry }: { report: AnomaliesReport | undefined; isPending: boolean; error: unknown; onRetry: () => void }) {
  const items = report ? [...report.expenses, ...report.duplicates] : [];
  const concentration = report?.concentration;
  return (
    <section aria-label="Anomalies" className="rounded-card border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold">Anomalies</h2>
      <p className="text-xs text-muted">{report ? `last ${report.window_days} days · as of ${report.as_of}` : "—"}</p>
      <QueryState isPending={isPending} error={error} onRetry={onRetry} skeletonClassName="mt-3 h-32 w-full">
        {items.length === 0 ? <p className="mt-3 text-sm text-muted">No anomalies in the window.</p> : (
          <ul className="mt-2 divide-y divide-border">
            {items.map((anomaly) => (
              <AnomalyRow key={`${anomaly.kind}-${anomaly.invoice}`} anomaly={anomaly} />
            ))}
          </ul>
        )}
        {concentration && (concentration.is_top1_flagged || concentration.is_top3_flagged) && (
          <p className="mt-3 flex items-start gap-2 text-xs text-warning">
            <PieChart size={14} strokeWidth={ICON_STROKE} className="mt-0.5 shrink-0" aria-hidden />
            Revenue concentration: top-1 {concentration.top1_party_name || "customer"} at {concentration.top1_share}, top-3 at {concentration.top3_share} (flags at 40% / 70%).
          </p>
        )}
      </QueryState>
    </section>
  );
}
