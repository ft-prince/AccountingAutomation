import { describe, expect, test } from "vitest";
import { anomalyAlerts, buildAlerts, draftsAlert, highRiskAlerts, itcAlerts, overdueAlerts } from "./dashboard-alerts";
import type { AgingReport, ItcAtRiskReport, ReportMeta } from "./reports";

const meta: ReportMeta = { fy: "2026-27", period: { from: "2026-04-01", to: "2026-09-04" }, basis: "accrual", invoice_count: 10, pending_count: 2 };

const aging: AgingReport = {
  rows: [
    { party: "p1", name: "Vedanta", "0-30": "10", "31-60": "20", "61-90": "30.50", "90+": "100", total: "160.50" },
    { party: "p2", name: "Clean", "0-30": "10", "31-60": "0", "61-90": "0", "90+": "0", total: "10" },
  ],
  totals: { "0-30": "20", "31-60": "20", "61-90": "30.50", "90+": "100", total: "170.50" },
  as_of: "2026-09-04",
  open_invoices: 3,
  meta,
};

const itc: ItcAtRiskReport = {
  blocks: [
    { reason: "missing_irn", count: 0, tax_at_risk: "0", invoices: [] },
    { reason: "blocked_category", count: 1, tax_at_risk: "970.20", invoices: [] },
  ],
  total_at_risk: "970.20",
  meta,
};

describe("dashboard alerts", () => {
  test("overdue alert sums only the 61-90 and 90+ buckets exactly", () => {
    const alerts = overdueAlerts(aging);
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toMatchObject({ kind: "overdue", amount: "130.50", href: "/parties/p1" });
  });

  test("ITC blocks with zero count are skipped", () => {
    const alerts = itcAlerts(itc);
    expect(alerts).toHaveLength(1);
    expect(alerts[0].title).toBe("ITC at risk · Blocked category");
  });

  test("feed orders overdue, high-risk, ITC, anomalies, then the drafts count", () => {
    const risk = [{ party: "p9", party_name: "Slow", score: "0.9", band: "high" as const, drivers: ["trend +12 d"], mean_days: "60", std_days: "5", trend_days: "12", share_overdue: "0.5", utilisation: null }];
    const anomalies = { as_of: "2026-09-04", window_days: 90, expenses: [{ invoice: "i1", kind: "amount" as const, party: "p1", party_name: "Vedanta", category: null, category_name: "", z: "3.4", detail: "3.4 MAD above median", related_invoice: null }], duplicates: [], concentration: { top1_party: null, top1_party_name: "", top1_share: "0", top3_parties: [], top3_share: "0", is_top1_flagged: false, is_top3_flagged: false } };
    const alerts = buildAlerts({ itc, arAging: aging, risk, anomalies, pendingDrafts: 2 });
    expect(alerts.map((alert) => alert.kind)).toEqual(["overdue", "high_risk", "itc_at_risk", "anomaly", "drafts"]);
    expect(highRiskAlerts(risk)[0]).toMatchObject({ title: "High payment risk · Slow", detail: "trend +12 d", href: "/parties/p9" });
    expect(anomalyAlerts(anomalies)[0]).toMatchObject({ title: "Anomaly · Amount · Vedanta", href: "/invoices/i1" });
    expect(draftsAlert(2)[0]).toMatchObject({ detail: "2 drafts waiting", tone: "warning" });
    expect(draftsAlert(0)[0]).toMatchObject({ detail: "queue is clear", tone: "muted" });
    expect(draftsAlert(undefined)).toEqual([]);
  });
});
