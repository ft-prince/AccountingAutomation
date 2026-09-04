"use client";

import { Play } from "lucide-react";
import { useState } from "react";
import { ChartFrame, ForecastBand } from "@/components/charts";
import { EmptyState } from "@/components/primitives/empty-state";
import { PageHeader } from "@/components/primitives/page-header";
import { StatTile } from "@/components/primitives/stat-tile";
import { Tabs } from "@/components/primitives/tabs";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api";
import { useUser } from "@/lib/auth";
import { ICON_STROKE } from "@/lib/constants";
import { useAnomalies, useCustomerRisk, useDrivers, useLatestForecast, useRunForecast, type ScenarioRunResult } from "@/lib/forecast";
import { HORIZONS, MIN_HISTORY_DAYS, horizonLabel, runwayLabel, type HorizonDays } from "@/lib/forecast-data";
import { formatDate } from "@/lib/format";
import { formatINR } from "@/lib/money";
import { todayIso } from "@/lib/periods";
import { toastApiError } from "@/lib/toast";
import type { Scenario } from "@/lib/types";
import { AnomaliesFeed } from "./anomalies-feed";
import { BacktestBadge } from "./backtest-badge";
import { DriversTable } from "./drivers-table";
import { NarrativePanel } from "./narrative-panel";
import { RecurringPanel } from "./recurring-panel";
import { RiskTable } from "./risk-table";
import { ScenariosPanel } from "./scenarios-panel";

const EDIT_ROLES: readonly string[] = ["owner", "accountant"];
const RATE_LIMIT_STATUS = 429;
const NOT_FOUND_STATUS = 404;
const CHART_HEIGHT = 320;
const HORIZON_ITEMS = HORIZONS.map((horizon) => ({ value: String(horizon.value) as `${HorizonDays}`, label: horizon.label }));

interface Overlay {
  scenario: Scenario;
  result: ScenarioRunResult;
}

/** §11 /forecast — band chart, runway, drivers, scenarios, backtest badge, recurring confirmations, anomalies. */
export function ForecastView({ today }: { today?: string }) {
  const { data: me } = useUser();
  const canEdit = EDIT_ROLES.includes(me?.role ?? "");
  const latest = useLatestForecast();
  const runForecast = useRunForecast();
  const drivers = useDrivers();
  const risk = useCustomerRisk();
  const anomalies = useAnomalies();
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const hasNoRun = latest.error instanceof ApiError && latest.error.status === NOT_FOUND_STATUS;
  const run = latest.data;
  const horizon = String(run?.horizon_days ?? HORIZONS[0].value) as `${HorizonDays}`;
  const todayDate = today ?? todayIso();

  const trigger = (horizonDays: number) =>
    runForecast.mutate(horizonDays, {
      onSuccess: () => { toast({ title: `Forecast run · ${horizonLabel(horizonDays)}` }); setOverlay(null); },
      onError: (error) => {
        if (error instanceof ApiError && error.status === RATE_LIMIT_STATUS) {
          toast({ variant: "destructive", title: "Too soon", description: "A run happened in the last 10 minutes; the latest result is shown." });
          return;
        }
        toastApiError(error, "Forecast run failed");
      },
    });

  const showBands = run ? !run.insufficient_history : false;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cashflow,"
        emphasis="forecast"
        description={run ? `as of ${formatDate(run.as_of)} · ${run.history_days} days of history · seed ${run.seed}` : "Deterministic scheduling + empirical distributions + Monte Carlo. Not AI forecasting (§8.1)."}
        actions={
          <>
            <Tabs items={HORIZON_ITEMS} value={horizon} onChange={(value) => trigger(Number(value))} ariaLabel="Horizon" />
            <Button onClick={() => trigger(Number(horizon))} disabled={runForecast.isPending}>
              <Play strokeWidth={ICON_STROKE} aria-hidden /> {runForecast.isPending ? "Running…" : "Run now"}
            </Button>
          </>
        }
      />

      {run?.insufficient_history && (
        <div role="status" className="rounded-card border border-warning bg-surface px-4 py-3 text-sm">
          <p className="font-medium text-warning">Insufficient history — deterministic view only</p>
          <p className="mt-1 text-xs text-muted">
            {run.history_days} days of confirmed history; P10–P90 bands and P50 need at least {MIN_HISTORY_DAYS} days of paid invoices so the days-to-pay distributions are real, not guessed (§8.1).
          </p>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,1fr)]">
        <ChartFrame
          title="Cashflow forecast"
          meta={undefined}
          periodLabel={run ? `${horizonLabel(run.horizon_days)} from ${formatDate(run.as_of)}${overlay ? ` · overlay: ${overlay.scenario.name}` : ""}` : "—"}
          isPending={latest.isPending}
          error={hasNoRun ? undefined : latest.error}
          isEmpty={hasNoRun || run?.points.length === 0}
          emptyText="No forecast run yet. Run one above."
          actions={run && showBands ? <BacktestBadge coverage={run.backtest_coverage} nOrigins={run.backtest_n_origins} mape={run.backtest_mape} /> : undefined}
        >
          {run && <ForecastBand points={run.points} today={todayDate} overlay={overlay?.result.points ?? []} showBands={showBands} height={CHART_HEIGHT} />}
        </ChartFrame>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <StatTile label="Runway" value={run ? (run.runway_date ? formatDate(run.runway_date) : runwayLabel(null)) : "—"} hint={run ? `cash stays positive ${run.runway_date ? "until then" : "through the horizon"}` : "run a forecast"} />
          <StatTile label="Opening cash" value={run ? formatINR(run.opening_cash) : "—"} hint={run ? `as of ${formatDate(run.as_of)}` : undefined} />
          {overlay && <StatTile label="Scenario runway" value={overlay.result.runway_date ? formatDate(overlay.result.runway_date) : runwayLabel(null)} hint={overlay.scenario.name} />}
        </div>
      </div>

      {!run && !latest.isPending && hasNoRun && <EmptyState icon={Play} title="No forecast yet" description="Run the engine once to see the band, drivers and runway." />}

      {run && <NarrativePanel key={run.id} runId={run.id} narrative={run.narrative} canGenerate={canEdit} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <DriversTable drivers={drivers.data} isPending={drivers.isPending} error={drivers.error} onRetry={() => void drivers.refetch()} />
        <ScenariosPanel canEdit={canEdit} activeScenarioId={overlay?.scenario.id ?? null} onOverlay={(scenario, result) => setOverlay(scenario && result ? { scenario, result } : null)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RecurringPanel canEdit={canEdit} />
        <AnomaliesFeed report={anomalies.data} isPending={anomalies.isPending} error={anomalies.error} onRetry={() => void anomalies.refetch()} />
      </div>

      <RiskTable rows={risk.data} isPending={risk.isPending} error={risk.error} onRetry={() => void risk.refetch()} />
    </div>
  );
}
