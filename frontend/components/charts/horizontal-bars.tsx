"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { shareBarPoints } from "@/lib/chart-data";
import type { PartyShareRow } from "@/lib/reports";
import { CHART_HEIGHT } from "./chart-frame";
import { useChartColors } from "./chart-colors";
import { MoneyTooltip, moneyTick } from "./money-tooltip";

const DEFAULT_LIMIT = 6;
const TEXT_KEYS = { amount: "amountText" };
const BAR_RADIUS: [number, number, number, number] = [0, 4, 4, 0];

/** Top customers by revenue (or vendors by spend) as horizontal accent bars. */
export function HorizontalBars({ rows, limit = DEFAULT_LIMIT, seriesName = "Revenue" }: { rows: readonly PartyShareRow[]; limit?: number; seriesName?: string }) {
  const colors = useChartColors();
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={shareBarPoints(rows, limit)} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }} barSize={14}>
        <CartesianGrid horizontal={false} stroke={colors.grid} />
        <XAxis type="number" tickFormatter={moneyTick} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" width={130} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip cursor={{ fill: colors.band }} content={(props) => <MoneyTooltip {...props} textKeys={TEXT_KEYS} />} />
        <Bar dataKey="amount" name={seriesName} fill={colors.accent} radius={BAR_RADIUS} />
      </BarChart>
    </ResponsiveContainer>
  );
}
