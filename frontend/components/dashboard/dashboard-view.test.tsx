import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import { DashboardView } from "./dashboard-view";

// Recharts needs layout; the charts are unit-tested through lib/chart-data. Here only the frame matters.
vi.mock("@/components/charts", () => ({
  ChartFrame: ({ title, children, actions }: { title: string; children: React.ReactNode; actions?: React.ReactNode }) => (
    <section aria-label={title}>{actions}{children}</section>
  ),
  PnlBars: () => <div data-testid="pnl" />,
  CategoryDonut: () => <div data-testid="donut" />,
  AgingStacked: () => <div data-testid="aging" />,
  HorizontalBars: () => <div data-testid="bars" />,
  ForecastBand: () => <div data-testid="forecast-band" />,
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

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/api/forecast/latest")) return json({ id: "run1", as_of: "2026-09-04", horizon_days: 91, insufficient_history: false, runway_date: null, backtest_coverage: "0.82", backtest_n_origins: 4, points: [{ date: "2026-09-05", p10: "1", p50: "2", p90: "3", deterministic: "2" }] });
    if (url.includes("/api/forecast/anomalies")) return json({ as_of: "2026-09-04", window_days: 90, expenses: [], duplicates: [{ invoice: "inv9", kind: "duplicate", party: "p", party_name: "Acme", category: null, category_name: "", z: null, detail: "same amount within 7 days", related_invoice: "inv8" }], concentration: { top1_party: null, top1_party_name: "", top1_share: "0", top3_parties: [], top3_share: "0", is_top1_flagged: false, is_top3_flagged: false } });
    if (url.includes("/api/forecast/risk/customers")) return json([{ party: "p7", party_name: "Slowpay Ltd", score: "0.91", band: "high", drivers: ["share overdue 60%"], mean_days: "70", std_days: "10", trend_days: "5", share_overdue: "0.6", utilisation: null }]);
    if (url.includes("/api/mail/review-queue")) return json([{ id: "d1" }, { id: "d2" }, { id: "d3" }]);
    if (url.includes("/api/mail/mailboxes")) return json({ count: 1, results: [{ id: "m1", provider: "gmail", email_address: "accounts@nexren.example", scopes: [], status: "active", has_send_scope: false, needs_send_scope: false, last_sync_at: new Date().toISOString(), last_error: "", connected_by: null }] });
    if (url.includes("/api/bank/statements")) return json({ count: 1, results: [{ id: "i1", bank_account: "a", filename: "hdfc-aug.pdf", format: "pdf", mapping: "hdfc", rows_total: 40, rows_imported: 38, rows_duplicate: 2, created_at: "2026-09-04T10:00:00Z" }] });
    if (url.includes("/api/notifications")) return json({ count: 1, results: [{ id: "n1", level: "warning", code: "backup_stale", title: "Backup is stale", body: "Last good backup 30 h ago", entity_type: "", entity_id: null, dedupe_key: "backup_stale", read_at: null, dismissed_at: null, created_at: "2026-09-04T10:00:00Z" }] });
    const name = /\/api\/reports\/([a-z-]+)/.exec(url)?.[1] ?? "";
    const body = REPORTS[name];
    if (!body) return new Response(JSON.stringify({ title: "Not found", status: 404 }), { status: 404 });
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

afterEach(() => vi.restoreAllMocks());

describe("DashboardView", () => {
  test("shows mailbox sync, last statement import and open reminders", async () => {
    mockFetch();
    renderWithClient(<DashboardView today="2026-09-04" />);
    expect(await screen.findByText("accounts@nexren.example")).toBeInTheDocument();
    expect(screen.getByText(/synced just now/)).toBeInTheDocument();
    expect(await screen.findByText("hdfc-aug.pdf")).toBeInTheDocument();
    expect(screen.getByText(/38 new · 2 duplicate of 40 · HDFC/)).toBeInTheDocument();
    expect(await screen.findByText("Backup is stale")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark read: Backup is stale" })).toBeInTheDocument();
  });

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
    expect(screen.getByText("> horizon")).toBeInTheDocument(); // runway tile from the latest run
    expect(screen.getByText("13w horizon · P50")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-band")).toBeInTheDocument();
    expect(screen.getByText("Bands calibrated · 82% coverage · 4 origins")).toBeInTheDocument();
    expect(screen.getByText("12 pending excluded")).toBeInTheDocument();
    expect(screen.getAllByText("Accrual · 12 pending").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("ITC at risk · Blocked category")).toBeInTheDocument();
    expect(screen.getByText("Drafts awaiting review")).toBeInTheDocument();
    expect(screen.getByText("3 drafts waiting")).toBeInTheDocument();
    expect(screen.getByText("Anomaly · Duplicate · Acme")).toBeInTheDocument();
    expect(screen.getByText("High payment risk · Slowpay Ltd")).toBeInTheDocument();

    // The picker drives every query with the same period.
    const urls = fetchSpy.mock.calls.map(([input]) => String(input)).filter((url) => url.includes("/api/reports/"));
    expect(urls.every((url) => url.includes("from=2026-04-01&to=2026-09-04&basis=accrual"))).toBe(true);
    expect(new Set(urls.map((url) => /reports\/([a-z-]+)/.exec(url)?.[1])).size).toBe(9);
  });
});
