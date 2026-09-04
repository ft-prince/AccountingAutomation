import { describe, expect, test } from "vitest";
import { buildAlerts, itcAlerts, overdueAlerts } from "./dashboard-alerts";
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

  test("feed ends with the Phase 16/18 placeholders", () => {
    const alerts = buildAlerts(itc, aging);
    expect(alerts.map((alert) => alert.kind)).toEqual(["overdue", "itc_at_risk", "placeholder", "placeholder"]);
  });
});
