// Pure builder for the §7.4 row-4 alerts feed: ITC at risk, overdue > 60 d, anomalies, high-risk
// customers and drafts awaiting review.
import Big from "big.js";
import type { AnomaliesReport, CustomerRisk } from "@/lib/forecast";
import type { AgingReport, ItcAtRiskReport } from "@/lib/reports";
import { humanize } from "@/lib/format";
import { orZero } from "@/lib/money";

export type AlertKind = "itc_at_risk" | "overdue" | "anomaly" | "high_risk" | "drafts";
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

export const ANOMALY_ALERT_LIMIT = 3;

export function anomalyAlerts(report: AnomaliesReport | undefined, limit = ANOMALY_ALERT_LIMIT): DashboardAlert[] {
  if (!report) return [];
  return [...report.duplicates, ...report.expenses].slice(0, limit).map((anomaly) => ({
    id: `anomaly-${anomaly.kind}-${anomaly.invoice}`,
    kind: "anomaly",
    tone: "warning",
    title: `Anomaly · ${humanize(anomaly.kind)} · ${anomaly.party_name || "unknown party"}`,
    detail: anomaly.detail,
    href: `/invoices/${anomaly.invoice}`,
  }));
}

export function highRiskAlerts(rows: readonly CustomerRisk[] | undefined): DashboardAlert[] {
  if (!rows) return [];
  return rows
    .filter((row) => row.band === "high")
    .map((row) => ({
      id: `risk-${row.party}`,
      kind: "high_risk",
      tone: "danger",
      title: `High payment risk · ${row.party_name || row.party}`,
      detail: row.drivers.length > 0 ? row.drivers.join(" · ") : `score ${row.score}`,
      href: `/parties/${row.party}`,
    }));
}

/** Count of drafts pending review (GET /api/mail/review-queue length); undefined while loading. */
export function draftsAlert(pendingCount: number | undefined): DashboardAlert[] {
  if (pendingCount === undefined) return [];
  return [{
    id: "drafts",
    kind: "drafts",
    tone: pendingCount > 0 ? "warning" : "muted",
    title: "Drafts awaiting review",
    detail: pendingCount === 0 ? "queue is clear" : `${pendingCount} draft${pendingCount === 1 ? "" : "s"} waiting`,
    href: "/inbox?status=awaiting_review",
  }];
}

export interface AlertSources {
  itc?: ItcAtRiskReport;
  arAging?: AgingReport;
  anomalies?: AnomaliesReport;
  risk?: readonly CustomerRisk[];
  pendingDrafts?: number;
}

export function buildAlerts(sources: AlertSources): DashboardAlert[] {
  return [...overdueAlerts(sources.arAging), ...highRiskAlerts(sources.risk), ...itcAlerts(sources.itc), ...anomalyAlerts(sources.anomalies), ...draftsAlert(sources.pendingDrafts)];
}
