// Pure: turns each §7.2 report response into flat tables (headers + string cells) that both the
// on-screen table and the client-side CSV export render. Money stays a decimal string throughout;
// `moneyColumns` marks which columns are rupee amounts so the table can format them.
import { AGING_BUCKETS, type ReportName, type ReportShapes } from "@/lib/reports";

export interface ReportTable {
  title: string;
  headers: readonly string[];
  rows: readonly (readonly string[])[];
  moneyColumns: readonly number[];
}

type Tabulator<N extends ReportName> = (data: ReportShapes[N]) => ReportTable[];

const tabulators: { [N in ReportName]: Tabulator<N> } = {
  summary: (data) => [
    {
      title: "Summary",
      headers: ["Measure", "Amount"],
      rows: [
        ["Revenue", data.revenue],
        ["Expenses", data.expenses],
        ["COGS", data.cogs],
        ["Gross margin", data.gross_margin],
        ["Gross margin %", `${data.gross_margin_pct}%`],
        ["Net", data.net],
        ["Tax payable", data.tax_payable],
        ["Pending (needs review) value", data.pending_value],
      ],
      moneyColumns: [1],
    },
  ],
  pnl: (data) => [
    {
      title: "P&L by month",
      headers: ["Month", "Revenue", "COGS", "Opex", "Net"],
      rows: data.rows.map((row) => [row.month, row.revenue, row.cogs, row.opex, row.net]),
      moneyColumns: [1, 2, 3, 4],
    },
  ],
  categories: (data) => [
    {
      title: "Expenses by category",
      headers: ["Category", "Amount", "Lines", "Previous period", "Delta"],
      rows: data.rows.map((row) => [row.category, row.amount, String(row.invoice_lines), row.previous, row.delta]),
      moneyColumns: [1, 3, 4],
    },
    {
      title: "Top movers",
      headers: ["Category", "Amount", "Lines", "Previous period", "Delta"],
      rows: data.top_movers.map((row) => [row.category, row.amount, String(row.invoice_lines), row.previous, row.delta]),
      moneyColumns: [1, 3, 4],
    },
  ],
  parties: (data) => [
    {
      title: `Top customers by revenue (top 1: ${data.concentration.top1_pct}%, top 3: ${data.concentration.top3_pct}%)`,
      headers: ["Customer", "Revenue", "Share %"],
      rows: data.top_customers.map((row) => [row.name, row.amount, row.share_pct]),
      moneyColumns: [1],
    },
    {
      title: "Top vendors by spend",
      headers: ["Vendor", "Spend", "Share %"],
      rows: data.top_vendors.map((row) => [row.name, row.amount, row.share_pct]),
      moneyColumns: [1],
    },
  ],
  "ar-aging": (data) => [agingTable("Receivables aging", "Customer", data)],
  "ap-aging": (data) => [agingTable("Payables aging", "Vendor", data)],
  "dso-dpo": (data) => [
    {
      title: `Trailing 90 days (${data.window.from} → ${data.window.to})`,
      headers: ["Measure", "Value"],
      rows: [
        ["DSO (days)", `${data.dso_days} days`],
        ["DPO (days)", `${data.dpo_days} days`],
        ["Receivables", data.receivables],
        ["Payables", data.payables],
        ["Sales, 90d", data.sales_90d],
        ["Purchases, 90d", data.purchases_90d],
      ],
      moneyColumns: [1],
    },
  ],
  "tax-liability": (data) => [
    {
      title: "Tax liability by period",
      headers: ["Period", "Output tax", "Eligible ITC", "Blocked ITC", "RCM", "Net payable", "GSTR-1 due", "GSTR-3B due"],
      rows: [
        ...data.rows.map((row) => [row.period, row.output_tax, row.eligible_itc, row.blocked_itc, row.rcm, row.net_payable, row.gstr1_due, row.gstr3b_due]),
        ["Total", data.totals.output_tax, data.totals.eligible_itc, data.totals.blocked_itc, data.totals.rcm, data.totals.net_payable, "", ""],
      ],
      moneyColumns: [1, 2, 3, 4, 5],
    },
    {
      title: "Upcoming returns",
      headers: ["Return", "Period", "Due", "Amount"],
      rows: data.upcoming.map((row) => [row.return, row.period, row.due, row.amount]),
      moneyColumns: [3],
    },
  ],
  "itc-at-risk": (data) => [
    {
      title: `ITC at risk (total ${data.total_at_risk})`,
      headers: ["Reason", "Invoices", "Tax at risk"],
      rows: data.blocks.map((block) => [block.reason, String(block.count), block.tax_at_risk]),
      moneyColumns: [2],
    },
    {
      title: "Invoices",
      headers: ["Reason", "Invoice", "Party", "Tax"],
      rows: data.blocks.flatMap((block) => block.invoices.map((invoice) => [block.reason, invoice.invoice_number, invoice.party, invoice.tax])),
      moneyColumns: [3],
    },
  ],
  "customer-profit": (data) => [
    {
      title: "Customer profitability",
      headers: ["Customer", "Revenue", "Attributed costs", "Profit"],
      rows: data.rows.map((row) => [row.name, row.revenue, row.attributed_costs, row.profit]),
      moneyColumns: [1, 2, 3],
    },
  ],
  "cash-position": (data) => [
    {
      title: `Cash position (total ${data.total_cash})`,
      headers: ["Account", "Balance", "As of", "Source", "Unmatched", "Unmatched credits", "Unmatched debits"],
      rows: data.accounts.map((row) => [row.name, row.balance, row.as_of, row.source, String(row.unmatched.count), row.unmatched.credits, row.unmatched.debits]),
      moneyColumns: [1, 5, 6],
    },
  ],
};

function agingTable(title: string, partyLabel: string, data: ReportShapes["ar-aging"]): ReportTable {
  return {
    title: `${title} as of ${data.as_of} (${data.open_invoices} open invoices)`,
    headers: [partyLabel, ...AGING_BUCKETS, "Total"],
    rows: [
      ...data.rows.map((row) => [row.name, ...AGING_BUCKETS.map((bucket) => row[bucket]), row.total]),
      ["Total", ...AGING_BUCKETS.map((bucket) => data.totals[bucket]), data.totals.total],
    ],
    moneyColumns: [1, 2, 3, 4, 5],
  };
}

export function tabulateReport<N extends ReportName>(name: N, data: ReportShapes[N]): ReportTable[] {
  const tabulate = tabulators[name] as Tabulator<N>;
  return tabulate(data);
}

/** All tables of a report as one CSV document: title line, header, rows, blank line between tables. */
export function reportTablesToCsvRows(tables: readonly ReportTable[]): { headers: readonly string[]; rows: readonly (readonly string[])[] } {
  const width = Math.max(...tables.map((table) => table.headers.length));
  const pad = (cells: readonly string[]) => [...cells, ...Array<string>(width - cells.length).fill("")];
  const rows = tables.flatMap((table, index) => [
    ...(index > 0 ? [pad([])] : []),
    pad([table.title]),
    pad(table.headers),
    ...table.rows.map(pad),
  ]);
  return { headers: rows[0] ?? [], rows: rows.slice(1) };
}
