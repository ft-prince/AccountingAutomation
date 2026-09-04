import { describe, expect, test } from "vitest";
import type { ReportMeta } from "@/lib/reports";
import { reportTablesToCsvRows, tabulateReport } from "./report-rows";

const meta: ReportMeta = { fy: "2026-27", period: { from: "2026-04-01", to: "2026-09-04" }, basis: "accrual", invoice_count: 10, pending_count: 2 };

describe("tabulateReport", () => {
  test("aging appends a totals row and keeps money as strings", () => {
    const tables = tabulateReport("ar-aging", {
      rows: [{ party: "p1", name: "Tata", "0-30": "100.00", "31-60": "0.00", "61-90": "0.00", "90+": "50.00", total: "150.00" }],
      totals: { "0-30": "100.00", "31-60": "0.00", "61-90": "0.00", "90+": "50.00", total: "150.00" },
      as_of: "2026-09-04",
      open_invoices: 1,
      meta,
    });
    expect(tables).toHaveLength(1);
    expect(tables[0].headers).toEqual(["Customer", "0-30", "31-60", "61-90", "90+", "Total"]);
    expect(tables[0].rows).toEqual([
      ["Tata", "100.00", "0.00", "0.00", "50.00", "150.00"],
      ["Total", "100.00", "0.00", "0.00", "50.00", "150.00"],
    ]);
  });

  test("itc-at-risk flattens invoices under their reason", () => {
    const tables = tabulateReport("itc-at-risk", {
      blocks: [{ reason: "missing_irn", count: 1, tax_at_risk: "18.00", invoices: [{ id: "i1", invoice_number: "INV-1", party: "Acme", tax: "18.00" }] }],
      total_at_risk: "18.00",
      meta,
    });
    expect(tables[1].rows).toEqual([["missing_irn", "INV-1", "Acme", "18.00"]]);
  });

  test("csv rows pad every table to the widest header and separate tables with a blank line", () => {
    const tables = tabulateReport("parties", {
      top_customers: [{ party: "p", name: "Tata", amount: "10.00", share_pct: "50.0" }],
      top_vendors: [],
      concentration: { top1_pct: "50.0", top3_pct: "50.0" },
      meta,
    });
    const csv = reportTablesToCsvRows(tables);
    expect(csv.headers).toEqual(["Top customers by revenue (top 1: 50.0%, top 3: 50.0%)", "", ""]);
    expect(csv.rows).toEqual([
      ["Customer", "Revenue", "Share %"],
      ["Tata", "10.00", "50.0"],
      ["", "", ""],
      ["Top vendors by spend", "", ""],
      ["Vendor", "Spend", "Share %"],
    ]);
  });
});
