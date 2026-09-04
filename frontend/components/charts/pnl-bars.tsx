"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pnlPoints } from "@/lib/chart-data";
import { formatMonth } from "@/lib/format";
import type { PnlRow } from "@/lib/reports";
import { CHART_HEIGHT } from "./chart-frame";
import { useChartColors } from "./chart-colors";
import { MoneyTooltip, moneyTick } from "./money-tooltip";

const TEXT_KEYS = { revenue: "revenueText", expenses: "expensesText" };
const BAR_RADIUS: [number, number, number, number] = [4, 4, 0, 0];

export function PnlBars({ rows }: { rows: readonly PnlRow[] }) {
  const colors = useChartColors();
  const data = pnlPoints(rows);
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data} barGap={2} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={colors.grid} />
        <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={moneyTick} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} width={64} />
        <Tooltip cursor={{ fill: colors.band }} content={(props) => <MoneyTooltip {...props} textKeys={TEXT_KEYS} />} />
        <Bar dataKey="revenue" name="Revenue" fill={colors.accent} radius={BAR_RADIUS} />
        <Bar dataKey="expenses" name="Expenses" fill={colors.comparison} radius={BAR_RADIUS} />
      </BarChart>
    </ResponsiveContainer>
  );
}
