// Pure builder for the §7.4 row-4 alerts feed. Anomalies and drafts arrive in Phases 16/18.
import Big from "big.js";
import type { AgingReport, ItcAtRiskReport } from "@/lib/reports";
import { humanize } from "@/lib/format";
import { orZero } from "@/lib/money";

export type AlertKind = "itc_at_risk" | "overdue" | "placeholder";
export type AlertTone = "danger" | "warning" | "muted";

export interface DashboardAlert {
  id: string;
  kind: AlertKind;
  tone: AlertTone;
  title: string;
  detail: string;
  /** Decimal string when the alert carries money. */
  amount?: string;
  href?: string;
}

const OVERDUE_BUCKETS = ["61-90", "90+"] as const;
export const OVERDUE_ALERT_LIMIT = 5;

export function itcAlerts(report: ItcAtRiskReport | undefined): DashboardAlert[] {
  if (!report) return [];
  return report.blocks
    .filter((block) => block.count > 0)
    .map((block) => ({
      id: `itc-${block.reason}`,
      kind: "itc_at_risk",
      tone: "warning",
      title: `ITC at risk · ${humanize(block.reason)}`,
      detail: `${block.count} invoice${block.count === 1 ? "" : "s"}`,
      amount: block.tax_at_risk,
      href: "/reports?tab=itc-at-risk",
    }));
}

/** Customers with receivables older than 60 days, largest first. */
export function overdueAlerts(report: AgingReport | undefined, limit = OVERDUE_ALERT_LIMIT): DashboardAlert[] {
  if (!report) return [];
  return report.rows
    .map((row) => ({ row, overdue: OVERDUE_BUCKETS.reduce((total, bucket) => total.plus(new Big(orZero(row[bucket]))), new Big(0)) }))
    .filter((entry) => entry.overdue.gt(0))
    .sort((a, b) => b.overdue.cmp(a.overdue))
    .slice(0, limit)
    .map(({ row, overdue }) => ({
      id: `overdue-${row.party}`,
      kind: "overdue",
      tone: "danger",
      title: `Overdue > 60 d · ${row.name}`,
      detail: `as of ${report.as_of}`,
      amount: overdue.toFixed(2),
      href: `/parties/${row.party}`,
    }));
}

export const PLACEHOLDER_ALERTS: readonly DashboardAlert[] = [
  { id: "drafts", kind: "placeholder", tone: "muted", title: "Drafts awaiting review", detail: "Phase 16 · client email assistant" },
  { id: "anomalies", kind: "placeholder", tone: "muted", title: "Anomalies", detail: "Phase 18 · forecasting" },
];

export function buildAlerts(itc: ItcAtRiskReport | undefined, arAging: AgingReport | undefined): DashboardAlert[] {
  return [...overdueAlerts(arAging), ...itcAlerts(itc), ...PLACEHOLDER_ALERTS];
}
