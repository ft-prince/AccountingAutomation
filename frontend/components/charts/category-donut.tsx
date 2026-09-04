"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { donutSlices } from "@/lib/chart-data";
import { formatINR } from "@/lib/money";
import type { CategoryRow } from "@/lib/reports";
import { CHART_HEIGHT } from "./chart-frame";
import { useChartColors } from "./chart-colors";

/** ≤ 5 slices + Other; tints of accent and ink-muted only (§7.4 row 3). */
export function CategoryDonut({ rows }: { rows: readonly CategoryRow[] }) {
  const colors = useChartColors();
  const slices = donutSlices(rows);
  return (
    <div className="grid h-[240px] grid-cols-[1fr_auto] items-center gap-4">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <PieChart>
          <Pie data={slices} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2} stroke={colors.surface} strokeWidth={2} isAnimationActive={false}>
            {slices.map((slice, index) => (
              <Cell key={slice.name} fill={colors.categorical[index % colors.categorical.length]} />
            ))}
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              const slice = payload?.[0]?.payload as { name: string; amount: string } | undefined;
              if (!active || !slice) return null;
              return (
                <div className="rounded-card border border-border bg-surface px-3 py-2 text-xs tabular-nums">
                  <span className="text-muted">{slice.name}</span> <span className="font-medium">{formatINR(slice.amount)}</span>
                </div>
              );
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="space-y-1.5 text-xs" aria-label="Categories">
        {slices.map((slice, index) => (
          <li key={slice.name} className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: colors.categorical[index % colors.categorical.length] }} aria-hidden />
            <span className="max-w-[9rem] truncate text-muted">{slice.name}</span>
            <span className="ml-auto pl-3 font-medium tabular-nums">{formatINR(slice.amount)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
