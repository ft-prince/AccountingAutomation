"use client";

import { StatTile } from "@/components/primitives/stat-tile";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/format";
import { formatINR } from "@/lib/money";
import type { AgingReport, CashPositionReport, SummaryReport, TaxLiabilityReport } from "@/lib/reports";

export interface KpiRowProps {
  periodLabel: string;
  cash: CashPositionReport | undefined;
  arAging: AgingReport | undefined;
  apAging: AgingReport | undefined;
  summary: SummaryReport | undefined;
  tax: TaxLiabilityReport | undefined;
}

function TileOrSkeleton({ label, value, hint }: { label: string; value: string | undefined; hint?: string }) {
  if (value === undefined) return <Skeleton className="h-[7.5rem] w-full" aria-busy />;
  return <StatTile label={label} value={value} hint={hint} />;
}

/** §7.4 row 1: cash · receivables · payables · net · tax due next · runway (Phase 18). */
export function KpiRow({ periodLabel, cash, arAging, apAging, summary, tax }: KpiRowProps) {
  const nextReturn = tax?.upcoming[0];
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6" aria-label="Key figures">
      <TileOrSkeleton label="Cash position" value={cash && formatINR(cash.total_cash)} hint={cash?.accounts[0] ? `as of ${formatDate(cash.accounts[0].as_of)}` : "no bank account"} />
      <TileOrSkeleton label="Receivables" value={arAging && formatINR(arAging.totals.total)} hint={arAging && `${arAging.open_invoices} open · as of ${formatDate(arAging.as_of)}`} />
      <TileOrSkeleton label="Payables" value={apAging && formatINR(apAging.totals.total)} hint={apAging && `${apAging.open_invoices} open`} />
      <TileOrSkeleton label={`Net · ${periodLabel}`} value={summary && formatINR(summary.net)} hint={summary && `${summary.meta.pending_count} pending excluded`} />
      <TileOrSkeleton
        label="Tax due next"
        value={tax ? (nextReturn ? formatINR(nextReturn.amount) : "—") : undefined}
        hint={nextReturn ? `${nextReturn.return} · ${formatDate(nextReturn.due)}` : "no upcoming return"}
      />
      <StatTile label="Runway" value="—" hint="Phase 18 · forecast" className="border-dashed" />
    </div>
  );
}
