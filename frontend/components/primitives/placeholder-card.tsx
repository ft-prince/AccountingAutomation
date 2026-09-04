import { Construction } from "lucide-react";
import { ICON_STROKE } from "@/lib/constants";
import { cn } from "@/lib/utils";

export interface PlaceholderCardProps {
  title: string;
  phase: number;
  description?: string;
  className?: string;
}

/** A labelled empty slot for a later phase, so the layout is final before the data exists. */
export function PlaceholderCard({ title, phase, description, className }: PlaceholderCardProps) {
  return (
    <section
      aria-label={`${title} · Phase ${phase}`}
      className={cn("flex flex-col items-center justify-center rounded-card border border-dashed border-border px-6 py-10 text-center", className)}
    >
      <Construction size={22} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
      <h3 className="mt-3 text-sm font-semibold">
        {title} <span className="font-normal text-muted">· Phase {phase}</span>
      </h3>
      {description && <p className="mt-1 max-w-xs text-xs text-muted">{description}</p>}
    </section>
  );
}
