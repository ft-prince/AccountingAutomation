"use client";

import { AlertTriangle, Clock, MailWarning, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { MoneyText } from "@/components/primitives/money-text";
import { ICON_STROKE } from "@/lib/constants";
import { buildAlerts, type AlertSources, type AlertTone, type DashboardAlert } from "@/lib/dashboard-alerts";
import type { ReportMeta } from "@/lib/reports";
import { BasisBadge } from "@/components/primitives/basis-badge";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<AlertTone, string> = { danger: "text-danger", warning: "text-warning", muted: "text-muted" };
const ICONS: Record<DashboardAlert["kind"], typeof AlertTriangle> = { overdue: Clock, itc_at_risk: AlertTriangle, anomaly: AlertTriangle, high_risk: ShieldAlert, drafts: MailWarning };

export function AlertsFeed({ sources, meta }: { sources: AlertSources; meta: ReportMeta | undefined }) {
  const alerts = buildAlerts(sources);
  return (
    <section aria-label="Alerts" className="flex flex-col rounded-card border border-border bg-surface p-5">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Alerts</h2>
          <p className="mt-0.5 text-xs text-muted">{meta ? `${meta.period.from} → ${meta.period.to}` : "—"}</p>
        </div>
        {meta && <BasisBadge basis={meta.basis} pendingCount={meta.pending_count} />}
      </header>
      <ul className="mt-4 divide-y divide-border">
        {alerts.map((alert) => {
          const Icon = ICONS[alert.kind];
          const body = (
            <>
              <Icon size={16} strokeWidth={ICON_STROKE} className={cn("mt-0.5 shrink-0", TONE_CLASS[alert.tone])} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{alert.title}</span>
                <span className="block text-xs text-muted">{alert.detail}</span>
              </span>
              {alert.amount && <MoneyText value={alert.amount} className={cn("text-sm font-medium", TONE_CLASS[alert.tone])} />}
            </>
          );
          return (
            <li key={alert.id} className="py-2.5">
              {alert.href ? (
                <Link href={alert.href} className="flex items-start gap-3 rounded-md hover:text-accent">
                  {body}
                </Link>
              ) : (
                <div className="flex items-start gap-3">{body}</div>
              )}
            </li>
          );
        })}
        {alerts.length === 0 && <li className="py-2.5 text-sm text-muted">Nothing needs attention.</li>}
      </ul>
    </section>
  );
}
