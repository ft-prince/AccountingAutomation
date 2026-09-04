"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDate } from "@/lib/format";
import { bandPoints } from "@/lib/forecast-data";
import type { ForecastPoint } from "@/lib/types";
import { CHART_HEIGHT } from "./chart-frame";
import { useChartColors } from "./chart-colors";
import { MoneyTooltip, moneyTick } from "./money-tooltip";

const TEXT_KEYS = { band: "p10Text", p50: "p50Text", deterministic: "deterministicText", overlay: "overlayText" };

export interface ForecastBandProps {
  points: readonly ForecastPoint[];
  /** ISO date drawn as the "today" reference line. */
  today: string;
  /** Scenario overlay P50 (ink-muted), joined by date. */
  overlay?: readonly ForecastPoint[];
  /** false ⇒ deterministic line only (§8.1 insufficient history). */
  showBands?: boolean;
  height?: number;
}

/** §9 charts: P10–P90 accent at 12%, P50 accent solid, deterministic ink dashed, zero line in danger. */
export function ForecastBand({ points, today, overlay = [], showBands = true, height = CHART_HEIGHT }: ForecastBandProps) {
  const colors = useChartColors();
  const data = bandPoints(points, overlay, showBands);
  // Recharts drops a category ReferenceLine whose x is absent; a run dated today starts at today+1.
  const todayX = data.some((point) => point.date === today) ? today : data[0]?.date;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={colors.grid} />
        <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={32} />
        <YAxis tickFormatter={moneyTick} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} width={72} />
        <Tooltip content={(props) => <MoneyTooltip {...props} textKeys={TEXT_KEYS} />} />
        <ReferenceLine y={0} stroke={colors.danger} strokeWidth={1} />
        {todayX && <ReferenceLine x={todayX} stroke={colors.muted} strokeDasharray="2 2" label={{ value: "today", fill: colors.muted, fontSize: 10, position: "insideTopRight" }} />}
        {showBands && <Area type="monotone" dataKey="band" name="P10–P90" stroke="none" fill={colors.band} isAnimationActive={false} connectNulls={false} />}
        {showBands && <Line type="monotone" dataKey="p50" name="P50" stroke={colors.accent} strokeWidth={2} dot={false} isAnimationActive={false} />}
        <Line type="monotone" dataKey="deterministic" name="Deterministic" stroke={colors.ink} strokeDasharray="5 4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        {overlay.length > 0 && <Line type="monotone" dataKey="overlay" name="Scenario P50" stroke={colors.comparisonSolid} strokeWidth={2} dot={false} isAnimationActive={false} data-series="overlay" />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
