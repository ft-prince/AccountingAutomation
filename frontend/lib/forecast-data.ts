// Pure reshaping for the §7.4 / §11 forecast band chart and its badges. Numbers here are
// geometry only (see lib/chart-data.ts); every label is formatted from the decimal string.
import Big from "big.js";
import { toChartNumber } from "@/lib/chart-data";
import { orZero } from "@/lib/money";
import type { ForecastPoint } from "@/lib/types";

export const HORIZONS = [
  { value: 91, label: "13w" },
  { value: 365, label: "12m" },
] as const;
export type HorizonDays = (typeof HORIZONS)[number]["value"];

/** §8.1: under 90 days of history the UI shows the deterministic line only. */
export const MIN_HISTORY_DAYS = 90;
/** §8.7 target coverage of actuals inside P10–P90. */
export const COVERAGE_MIN = new Big("0.75");
export const COVERAGE_MAX = new Big("0.90");

export interface BandPoint {
  date: string;
  /** [p10, p90] for the Area range; absent when the run has no bands. */
  band?: [number, number];
  p50?: number;
  deterministic: number;
  overlay?: number;
  p10Text?: string;
  p50Text?: string;
  p90Text?: string;
  deterministicText: string;
  overlayText?: string;
}

function textOrUndefined(value: string | null | undefined): string | undefined {
  return value === null || value === undefined ? undefined : value;
}

/** Merges the base run with an optional scenario overlay (P50 only) keyed by date. */
export function bandPoints(points: readonly ForecastPoint[], overlay: readonly ForecastPoint[] = [], showBands = true): BandPoint[] {
  const overlayByDate = new Map(overlay.map((point) => [point.date, point.p50 ?? point.deterministic]));
  return points.map((point) => {
    const hasBand = showBands && point.p10 !== null && point.p10 !== undefined && point.p90 !== null && point.p90 !== undefined;
    const overlayValue = overlayByDate.get(point.date);
    return {
      date: point.date,
      band: hasBand ? [toChartNumber(point.p10), toChartNumber(point.p90)] : undefined,
      p50: showBands && point.p50 !== null && point.p50 !== undefined ? toChartNumber(point.p50) : undefined,
      deterministic: toChartNumber(point.deterministic),
      overlay: overlayValue === null || overlayValue === undefined ? undefined : toChartNumber(overlayValue),
      p10Text: hasBand ? textOrUndefined(point.p10) : undefined,
      p50Text: showBands ? textOrUndefined(point.p50) : undefined,
      p90Text: hasBand ? textOrUndefined(point.p90) : undefined,
      deterministicText: orZero(point.deterministic),
      overlayText: overlayValue === null || overlayValue === undefined ? undefined : overlayValue,
    };
  });
}

export interface BacktestBadge {
  label: string;
  tone: "success" | "warning" | "muted";
  isCalibrated: boolean;
}

/** "0.82" → "Bands calibrated · 82% coverage"; outside 75–90% → "Bands miscalibrated · N% coverage". */
export function backtestBadge(coverage: string | null | undefined, nOrigins: number | null | undefined = null): BacktestBadge {
  if (coverage === null || coverage === undefined || coverage === "") {
    return { label: "No backtest yet", tone: "muted", isCalibrated: false };
  }
  const value = new Big(coverage);
  const percent = value.times(100).round(0).toString();
  const isCalibrated = value.gte(COVERAGE_MIN) && value.lte(COVERAGE_MAX);
  const origins = nOrigins ? ` · ${nOrigins} origins` : "";
  return isCalibrated
    ? { label: `Bands calibrated · ${percent}% coverage${origins}`, tone: "success", isCalibrated }
    : { label: `Bands miscalibrated · ${percent}% coverage${origins}`, tone: "warning", isCalibrated };
}

/** Runway tile headline: the date cash goes negative, or "> horizon" when it never does. */
export function runwayLabel(runwayDate: string | null | undefined): string {
  return runwayDate ? runwayDate : "> horizon";
}

export function horizonLabel(horizonDays: number): string {
  return HORIZONS.find((horizon) => horizon.value === horizonDays)?.label ?? `${horizonDays}d`;
}
