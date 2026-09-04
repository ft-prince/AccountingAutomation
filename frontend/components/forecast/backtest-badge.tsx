import { StatusBadge } from "@/components/primitives/status-badge";
import { backtestBadge } from "@/lib/forecast-data";

/** §8.7 calibration badge: success inside 75–90% coverage, warning outside, muted when unscored. */
export function BacktestBadge({ coverage, nOrigins, mape }: { coverage: string | null | undefined; nOrigins?: number | null; mape?: string | null }) {
  const badge = backtestBadge(coverage, nOrigins);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <StatusBadge status={badge.isCalibrated ? "calibrated" : "miscalibrated"} tone={badge.tone} label={badge.label} />
      {mape && <span className="text-xs text-muted tabular-nums">MAPE {mape}</span>}
    </span>
  );
}
