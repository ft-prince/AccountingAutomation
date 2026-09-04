import { StatusBadge, type StatusTone } from "@/components/primitives/status-badge";
import type { RiskBand } from "@/lib/forecast";

// §8.5 bands: low / watch / high — semantic colour is status, so it is permitted here.
const BAND_TONE: Record<RiskBand, StatusTone> = { low: "success", watch: "warning", high: "danger" };
const BAND_LABEL: Record<RiskBand, string> = { low: "Low risk", watch: "Watch", high: "High risk" };

export function RiskBandBadge({ band, className }: { band: RiskBand | null | undefined; className?: string }) {
  if (!band) return <StatusBadge status="unscored" tone="muted" label="Not scored" className={className} />;
  return <StatusBadge status={band} tone={BAND_TONE[band]} label={BAND_LABEL[band]} className={className} />;
}
