"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ReportBasis } from "@/components/primitives/basis-badge";
import { buildQuery } from "@/lib/query";

// PROJECT_SPECS §7.2 report shapes. The reports view is untyped in the OpenAPI schema (a single
// /api/reports/{name} operation), so these mirror apps/reporting responses field-for-field.
// Money is always a decimal string.

export interface ReportMeta {
  fy: string;
  period: { from: string; to: string };
  basis: ReportBasis;
  invoice_count: number;
  pending_count: number;
}

export interface ReportParams {
  from: string;
  to: string;
  basis: ReportBasis;
}

export interface SummaryReport {
  revenue: string;
  expenses: string;
  cogs: string;
  gross_margin: string;
  gross_margin_pct: string;
  net: string;
  tax_payable: string;
  pending_value: string;
  meta: ReportMeta;
}

export interface PnlRow {
  month: string;
  revenue: string;
  cogs: string;
  opex: string;
  net: string;
}
export interface PnlReport {
  rows: PnlRow[];
  meta: ReportMeta;
}

export interface CategoryRow {
  category: string;
  amount: string;
  invoice_lines: number;
  previous: string;
  delta: string;
}
export interface CategoriesReport {
  rows: CategoryRow[];
  top_movers: CategoryRow[];
  meta: ReportMeta;
}

export interface PartyShareRow {
  party: string;
  name: string;
  amount: string;
  share_pct: string;
}
export interface PartiesReport {
  top_customers: PartyShareRow[];
  top_vendors: PartyShareRow[];
  concentration: { top1_pct: string; top3_pct: string };
  meta: ReportMeta;
}

export const AGING_BUCKETS = ["0-30", "31-60", "61-90", "90+"] as const;
export type AgingBucket = (typeof AGING_BUCKETS)[number];
export type AgingRow = { party: string; name: string; total: string } & Record<AgingBucket, string>;
export interface AgingReport {
  rows: AgingRow[];
  totals: Record<AgingBucket, string> & { total: string };
  as_of: string;
  open_invoices: number;
  meta: ReportMeta;
}

export interface DsoDpoReport {
  dso_days: string;
  dpo_days: string;
  receivables: string;
  payables: string;
  meta: ReportMeta;
}

export interface TaxLiabilityRow {
  period: string;
  output_tax: string;
  eligible_itc: string;
  blocked_itc: string;
  rcm: string;
  net_payable: string;
  gstr1_due: string;
  gstr3b_due: string;
}
export interface UpcomingReturn {
  return: string;
  period: string;
  due: string;
  amount: string;
}
export interface TaxLiabilityReport {
  rows: TaxLiabilityRow[];
  totals: Omit<TaxLiabilityRow, "period" | "gstr1_due" | "gstr3b_due">;
  upcoming: UpcomingReturn[];
  meta: ReportMeta;
}

export interface ItcRiskInvoice {
  id: string;
  invoice_number: string;
  party: string;
  tax: string;
}
export interface ItcRiskBlock {
  reason: string;
  count: number;
  tax_at_risk: string;
  invoices: ItcRiskInvoice[];
}
export interface ItcAtRiskReport {
  blocks: ItcRiskBlock[];
  total_at_risk: string;
  meta: ReportMeta;
}

export interface CustomerProfitRow {
  party: string;
  name: string;
  revenue: string;
  attributed_costs: string;
  profit: string;
}
export interface CustomerProfitReport {
  rows: CustomerProfitRow[];
  meta: ReportMeta;
}

export interface CashAccountRow {
  account: string;
  name: string;
  balance: string;
  as_of: string;
  source: string;
  unmatched: { count: number; credits: string; debits: string };
}
export interface CashPositionReport {
  accounts: CashAccountRow[];
  total_cash: string;
  meta: ReportMeta;
}

export interface ReportShapes {
  summary: SummaryReport;
  pnl: PnlReport;
  categories: CategoriesReport;
  parties: PartiesReport;
  "ar-aging": AgingReport;
  "ap-aging": AgingReport;
  "dso-dpo": DsoDpoReport;
  "tax-liability": TaxLiabilityReport;
  "itc-at-risk": ItcAtRiskReport;
  "customer-profit": CustomerProfitReport;
  "cash-position": CashPositionReport;
}
export type ReportName = keyof ReportShapes;

export const REPORT_NAMES: readonly ReportName[] = [
  "summary",
  "pnl",
  "categories",
  "parties",
  "ar-aging",
  "ap-aging",
  "dso-dpo",
  "tax-liability",
  "itc-at-risk",
  "customer-profit",
  "cash-position",
];

export function reportPath(name: ReportName, params: ReportParams): string {
  return `/api/reports/${name}${buildQuery({ from: params.from, to: params.to, basis: params.basis })}`;
}

export const REPORT_STALE_MS = 30_000;

export function useReport<N extends ReportName>(name: N, params: ReportParams, enabled = true) {
  return useQuery({
    queryKey: ["reports", name, params],
    queryFn: () => api<ReportShapes[N]>(reportPath(name, params)),
    staleTime: REPORT_STALE_MS,
    enabled,
  });
}
