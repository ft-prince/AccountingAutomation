import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { ICON_STROKE } from "@/lib/constants";
import { cn } from "@/lib/utils";

export type DeltaDirection = "up" | "down" | "flat";

export interface StatTileProps {
  label: string;
  /** Already formatted display string (use MoneyText output or a percentage). */
  value: string;
  delta?: { value: string; direction: DeltaDirection };
  hint?: string;
  className?: string;
}

// §9: semantic colours only for status — success/danger carry direction, flat stays muted.
const DELTA_STYLES: Record<DeltaDirection, { chip: string; Icon: typeof ArrowUpRight }> = {
  up: { chip: "text-success border-success", Icon: ArrowUpRight },
  down: { chip: "text-danger border-danger", Icon: ArrowDownRight },
  flat: { chip: "text-muted border-border", Icon: Minus },
};

export function StatTile({ label, value, delta, hint, className }: StatTileProps) {
  const deltaStyle = delta ? DELTA_STYLES[delta.direction] : null;
  return (
    <div className={cn("lift rounded-card border border-border bg-surface p-5", className)}>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 font-display text-3xl italic leading-none tracking-tight tabular-nums">{value}</p>
      {(delta || hint) && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {delta && deltaStyle && (
            <span
              data-direction={delta.direction}
              className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 tabular-nums", deltaStyle.chip)}
            >
              <deltaStyle.Icon size={12} strokeWidth={ICON_STROKE} aria-hidden />
              {delta.value}
            </span>
          )}
          {hint && <span className="text-muted">{hint}</span>}
        </div>
      )}
    </div>
  );
}
