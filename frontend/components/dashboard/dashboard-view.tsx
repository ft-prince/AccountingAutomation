"use client";

import { useState } from "react";
import { AgingStacked, CategoryDonut, ChartFrame, HorizontalBars, PnlBars } from "@/components/charts";
import { PageHeader } from "@/components/primitives/page-header";
import { PeriodPicker } from "@/components/primitives/period-picker";
import { PlaceholderCard } from "@/components/primitives/placeholder-card";
import { resolvePeriod, todayIso, type Period } from "@/lib/periods";
import { useReport, type ReportParams } from "@/lib/reports";
import { AlertsFeed } from "./alerts-feed";
import { KpiRow } from "./kpi-row";

const DASHBOARD_BASIS = "accrual";

/** §7.4 — every query is driven by the one PeriodPicker; every chart states period + pending count. */
export function DashboardView({ today }: { today?: string }) {
  const [period, setPeriod] = useState<Period>(() => resolvePeriod("fy_to_date", today ?? todayIso()));
  const params: ReportParams = { from: period.from, to: period.to, basis: DASHBOARD_BASIS };

  const summary = useReport("summary", params);
  const pnl = useReport("pnl", params);
  const categories = useReport("categories", params);
  const parties = useReport("parties", params);
  const arAging = useReport("ar-aging", params);
  const apAging = useReport("ap-aging", params);
  const tax = useReport("tax-liability", params);
  const itc = useReport("itc-at-risk", params);
  const cash = useReport("cash-position", params);

  return (
    <div className="space-y-6">
      <PageHeader title="Cashflow," emphasis="forecast" description={`${period.label} · ${DASHBOARD_BASIS} basis`} actions={<PeriodPicker onChange={setPeriod} defaultPreset="fy_to_date" today={today} />} />

      <KpiRow periodLabel={period.label} cash={cash.data} arAging={arAging.data} apAging={apAging.data} summary={summary.data} tax={tax.data} />

      <PlaceholderCard title="Cashflow forecast" phase={18} description="13-week P10–P90 band from Module D lands here." className="min-h-[200px]" />

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartFrame title="P&L by month" meta={pnl.data?.meta} periodLabel={period.label} isPending={pnl.isPending} error={pnl.error} isEmpty={pnl.data?.rows.length === 0}>
          {pnl.data && <PnlBars rows={pnl.data.rows} />}
        </ChartFrame>
        <ChartFrame title="Expenses by category" meta={categories.data?.meta} periodLabel={period.label} isPending={categories.isPending} error={categories.error} isEmpty={categories.data?.rows.length === 0}>
          {categories.data && <CategoryDonut rows={categories.data.rows} />}
        </ChartFrame>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ChartFrame title="AR aging" meta={arAging.data?.meta} periodLabel={arAging.data ? `as of ${arAging.data.as_of}` : period.label} isPending={arAging.isPending} error={arAging.error} isEmpty={arAging.data?.rows.length === 0}>
          {arAging.data && <AgingStacked rows={arAging.data.rows} />}
        </ChartFrame>
        <ChartFrame title="Top customers" meta={parties.data?.meta} periodLabel={period.label} isPending={parties.isPending} error={parties.error} isEmpty={parties.data?.top_customers.length === 0}>
          {parties.data && <HorizontalBars rows={parties.data.top_customers} />}
        </ChartFrame>
        <AlertsFeed itc={itc.data} arAging={arAging.data} meta={itc.data?.meta ?? arAging.data?.meta} />
      </div>
    </div>
  );
}
