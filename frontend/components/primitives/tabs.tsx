"use client";

import { cn } from "@/lib/utils";

export interface TabItem<T extends string> {
  value: T;
  label: string;
  /** Rendered as a muted suffix, e.g. "Phase 16". */
  hint?: string;
}

export interface TabsProps<T extends string> {
  items: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  className?: string;
}

/** Accessible pill tabs (no Radix dependency). The active tab is the single accent per view (§9). */
export function Tabs<T extends string>({ items, value, onChange, ariaLabel, className }: TabsProps<T>) {
  return (
    <div role="tablist" aria-label={ariaLabel} className={cn("flex flex-wrap gap-1 rounded-full border border-border bg-surface p-1", className)}>
      {items.map((item) => {
        const isActive = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(item.value)}
            className={cn(
              "rounded-full px-3 py-1.5 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              isActive ? "bg-primary text-primary-foreground" : "text-muted hover:text-foreground",
            )}
          >
            {item.label}
            {item.hint && <span className={cn("ml-1 text-xs", isActive ? "opacity-80" : "text-muted")}>· {item.hint}</span>}
          </button>
        );
      })}
    </div>
  );
}
