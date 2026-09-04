"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toChartNumber } from "@/lib/chart-data";
import { AGING_BUCKETS, type AgingRow } from "@/lib/reports";
import { CHART_HEIGHT } from "./chart-frame";
import { useChartColors } from "./chart-colors";
import { MoneyTooltip, moneyTick } from "./money-tooltip";

const ROW_LIMIT = 8;
const TEXT_KEYS = Object.fromEntries(AGING_BUCKETS.map((bucket) => [bucket, `${bucket}Text`]));

function points(rows: readonly AgingRow[]) {
  return rows.slice(0, ROW_LIMIT).map((row) => ({
    name: row.name,
    ...Object.fromEntries(AGING_BUCKETS.flatMap((bucket) => [
      [bucket, toChartNumber(row[bucket])],
      [`${bucket}Text`, row[bucket]],
    ])),
  }));
}

/** Receivables per customer stacked by bucket; buckets deepen towards 90+ (§7.4 row 4). */
export function AgingStacked({ rows }: { rows: readonly AgingRow[] }) {
  const colors = useChartColors();
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={points(rows)} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }} barSize={14}>
        <CartesianGrid horizontal={false} stroke={colors.grid} />
        <XAxis type="number" tickFormatter={moneyTick} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" width={120} tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip cursor={{ fill: colors.band }} content={(props) => <MoneyTooltip {...props} textKeys={TEXT_KEYS} />} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, color: colors.muted }} />
        {AGING_BUCKETS.map((bucket, index) => (
          <Bar key={bucket} dataKey={bucket} name={`${bucket} d`} stackId="aging" fill={colors.aging[index]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
