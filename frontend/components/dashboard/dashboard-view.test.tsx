import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import { DashboardView } from "./dashboard-view";

// Recharts needs layout; the charts are unit-tested through lib/chart-data. Here only the frame matters.
vi.mock("@/components/charts", () => ({
  ChartFrame: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <section aria-label={title}>{children}</section>
  ),
  PnlBars: () => <div data-testid="pnl" />,
  CategoryDonut: () => <div data-testid="donut" />,
  AgingStacked: () => <div data-testid="aging" />,
  HorizontalBars: () => <div data-testid="bars" />,
}));

const meta = { fy: "2026-27", period: { from: "2026-04-01", to: "2026-09-04" }, basis: "accrual", invoice_count: 182, pending_count: 12 };

const REPORTS: Record<string, unknown> = {
  summary: { revenue: "1", expenses: "1", cogs: "0", gross_margin: "1", gross_margin_pct: "1", net: "31770377.00", tax_payable: "1", pending_value: "435177.00", meta },
  pnl: { rows: [{ month: "2026-04", revenue: "10", cogs: "1", opex: "1", net: "8" }], meta },
  categories: { rows: [{ category: "Rent", amount: "10", invoice_lines: 1, previous: "0", delta: "10" }], top_movers: [], meta },
  parties: { top_customers: [{ party: "p", name: "Tata", amount: "10", share_pct: "50" }], top_vendors: [], concentration: { top1_pct: "50", top3_pct: "50" }, meta },
  "ar-aging": { rows: [], totals: { "0-30": "0", "31-60": "0", "61-90": "0", "90+": "0", total: "12792026.00" }, as_of: "2026-09-04", open_invoices: 50, meta },
  "ap-aging": { rows: [], totals: { "0-30": "0", "31-60": "0", "61-90": "0", "90+": "0", total: "287028.00" }, as_of: "2026-09-04", open_invoices: 4, meta },
  "tax-liability": { rows: [], totals: { output_tax: "0", eligible_itc: "0", blocked_itc: "0", rcm: "0", net_payable: "0" }, upcoming: [{ return: "GSTR-1", period: "2026-08", due: "2026-09-11", amount: "1138221.00" }], meta },
  "itc-at-risk": { blocks: [{ reason: "blocked_category", count: 1, tax_at_risk: "970.20", invoices: [] }], total_at_risk: "970.20", meta },
  "cash-position": { accounts: [{ account: "a", name: "HDFC Current", balance: "90586823.00", as_of: "2026-09-04", source: "statement", unmatched: { count: 8, credits: "1", debits: "-1" } }], total_cash: "90586823.00", meta },
};

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const name = /\/api\/reports\/([a-z-]+)/.exec(url)?.[1] ?? "";
    const body = REPORTS[name];
    if (!body) return new Response(JSON.stringify({ title: "Not found", status: 404 }), { status: 404 });
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

afterEach(() => vi.restoreAllMocks());

describe("DashboardView", () => {
  test("renders KPI tiles from the reports and states the pending count on every chart", async () => {
    // Arrange
    const fetchSpy = mockFetch();

    // Act
    renderWithClient(<DashboardView today="2026-09-04" />);

    // Assert
    await waitFor(() => expect(screen.getByText("₹9,05,86,823.00")).toBeInTheDocument());
    expect(screen.getByText("₹1,27,92,026.00")).toBeInTheDocument(); // receivables
    expect(screen.getByText("₹2,87,028.00")).toBeInTheDocument(); // payables
    expect(screen.getByText("₹3,17,70,377.00")).toBeInTheDocument(); // net
    expect(screen.getByText("₹11,38,221.00")).toBeInTheDocument(); // tax due next
    expect(screen.getByText("GSTR-1 · 11 Sep 2026")).toBeInTheDocument();
    expect(screen.getByText("Phase 18 · forecast")).toBeInTheDocument(); // runway placeholder
    expect(screen.getByText("12 pending excluded")).toBeInTheDocument();
    expect(screen.getAllByText("Accrual · 12 pending").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("ITC at risk · Blocked category")).toBeInTheDocument();
    expect(screen.getByText("Drafts awaiting review")).toBeInTheDocument();

    // The picker drives every query with the same period.
    const urls = fetchSpy.mock.calls.map(([input]) => String(input));
    expect(urls.every((url) => url.includes("from=2026-04-01&to=2026-09-04&basis=accrual"))).toBe(true);
    expect(new Set(urls.map((url) => /reports\/([a-z-]+)/.exec(url)?.[1])).size).toBe(9);
  });
});
