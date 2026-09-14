"use client";

import { useState } from "react";
import { AgingStacked, CategoryDonut, ChartFrame, ForecastBand, HorizontalBars, PnlBars } from "@/components/charts";
import { BacktestBadge } from "@/components/forecast/backtest-badge";
import { PageHeader } from "@/components/primitives/page-header";
import { PeriodPicker } from "@/components/primitives/period-picker";
import { resolvePeriod, todayIso, type Period } from "@/lib/periods";
import { ApiError } from "@/lib/api";
import { useAnomalies, useCustomerRisk, useLatestForecast } from "@/lib/forecast";
import { horizonLabel } from "@/lib/forecast-data";
import { useReviewQueue } from "@/lib/mail";
import { useReport, type ReportParams } from "@/lib/reports";
import { AlertsFeed } from "./alerts-feed";
import { ConnectionsPanel } from "./connections-panel";
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
  const forecast = useLatestForecast();
  const anomalies = useAnomalies();
  const risk = useCustomerRisk();
  const reviewQueue = useReviewQueue();
  const hasNoRun = forecast.error instanceof ApiError && forecast.error.status === 404;
  const latestRun = forecast.data ?? (hasNoRun ? null : undefined);
  const todayDate = today ?? todayIso();

  return (
    <div className="space-y-6">
      <PageHeader title="Cashflow," emphasis="forecast" description={`${period.label} · ${DASHBOARD_BASIS} basis`} actions={<PeriodPicker onChange={setPeriod} defaultPreset="fy_to_date" today={today} />} />

      <ConnectionsPanel />

      <KpiRow periodLabel={period.label} cash={cash.data} arAging={arAging.data} apAging={apAging.data} summary={summary.data} tax={tax.data} forecast={forecast.isError && !hasNoRun ? null : latestRun} />

      <ChartFrame
        title="Cashflow forecast"
        meta={undefined}
        periodLabel={forecast.data ? `${horizonLabel(forecast.data.horizon_days)} from ${forecast.data.as_of} · ${forecast.data.insufficient_history ? "deterministic only (< 90 d history)" : "P10–P90 band"}` : "—"}
        isPending={forecast.isPending}
        error={hasNoRun ? undefined : forecast.error}
        isEmpty={hasNoRun || forecast.data?.points.length === 0}
        emptyText="No forecast run yet — open Forecast and run one."
        actions={forecast.data && !forecast.data.insufficient_history ? <BacktestBadge coverage={forecast.data.backtest_coverage} nOrigins={forecast.data.backtest_n_origins} /> : undefined}
      >
        {forecast.data && <ForecastBand points={forecast.data.points} today={todayDate} showBands={!forecast.data.insufficient_history} />}
      </ChartFrame>

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
        <AlertsFeed sources={{ itc: itc.data, arAging: arAging.data, anomalies: anomalies.data, risk: risk.data, pendingDrafts: reviewQueue.data?.length }} meta={itc.data?.meta ?? arAging.data?.meta} />
      </div>
    </div>
  );
}
