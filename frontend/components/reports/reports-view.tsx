"use client";

import { FileDown } from "lucide-react";
import { useState } from "react";
import { BasisBadge, type ReportBasis } from "@/components/primitives/basis-badge";
import { PageHeader } from "@/components/primitives/page-header";
import { PeriodPicker } from "@/components/primitives/period-picker";
import { QueryState } from "@/components/primitives/query-state";
import { Tabs } from "@/components/primitives/tabs";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { downloadCsv, toCsv } from "@/lib/csv";
import { resolvePeriod, todayIso, type Period } from "@/lib/periods";
import { useReport, type ReportName, type ReportParams } from "@/lib/reports";
import { ExportsPanel } from "./exports-panel";
import { reportTablesToCsvRows, tabulateReport } from "./report-rows";
import { ReportTable } from "./report-table";

export const REPORT_TABS: readonly { value: ReportName; label: string }[] = [
  { value: "summary", label: "Summary" },
  { value: "pnl", label: "P&L" },
  { value: "categories", label: "Categories" },
  { value: "parties", label: "Parties" },
  { value: "ar-aging", label: "AR aging" },
  { value: "ap-aging", label: "AP aging" },
  { value: "dso-dpo", label: "DSO / DPO" },
  { value: "tax-liability", label: "Tax liability" },
  { value: "itc-at-risk", label: "ITC at risk" },
  { value: "customer-profit", label: "Customer profit" },
  { value: "cash-position", label: "Cash position" },
];

const BASIS_TABS: readonly { value: ReportBasis; label: string }[] = [
  { value: "accrual", label: "Accrual" },
  { value: "cash", label: "Cash" },
];

/** §7.2 / §11 — every report as a tab, one PeriodPicker and basis toggle driving the query, CSV export of rendered rows. */
export function ReportsView({ today, initialReport = "summary" }: { today?: string; initialReport?: ReportName }) {
  const [report, setReport] = useState<ReportName>(initialReport);
  const [basis, setBasis] = useState<ReportBasis>("accrual");
  const [period, setPeriod] = useState<Period>(() => resolvePeriod("fy_to_date", today ?? todayIso()));
  const params: ReportParams = { fy: period.fy, from: period.from, to: period.to, basis };
  const query = useReport(report, params);
  const tables = query.data ? tabulateReport(report, query.data) : [];

  const exportCsv = () => {
    const { headers, rows } = reportTablesToCsvRows(tables);
    downloadCsv(`${report}_${period.from}_${period.to}_${basis}.csv`, toCsv(headers, rows));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports,"
        emphasis="stated"
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            {period.label}
            {query.data && <BasisBadge basis={query.data.meta.basis} pendingCount={query.data.meta.pending_count} />}
            {query.data && <span>{query.data.meta.invoice_count} confirmed invoices · FY{query.data.meta.fy}</span>}
          </span>
        }
        actions={
          <>
            <PeriodPicker onChange={setPeriod} defaultPreset="fy_to_date" today={today} />
            <Tabs items={BASIS_TABS} value={basis} onChange={setBasis} ariaLabel="Basis" />
            <Button variant="outline" onClick={exportCsv} disabled={tables.length === 0}>
              <FileDown size={16} strokeWidth={ICON_STROKE} aria-hidden /> Export CSV
            </Button>
          </>
        }
      />

      <Tabs items={REPORT_TABS} value={report} onChange={setReport} ariaLabel="Report" />

      <QueryState isPending={query.isPending} error={query.error} onRetry={() => void query.refetch()}>
        <div className="space-y-4">
          {tables.map((table) => (
            <ReportTable key={table.title} table={table} />
          ))}
        </div>
      </QueryState>

      <ExportsPanel defaultMonth={period.to} range={{ from: period.from, to: period.to }} />
    </div>
  );
}
