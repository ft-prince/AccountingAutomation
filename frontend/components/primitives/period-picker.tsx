"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { PERIOD_PRESETS, resolvePeriod, todayIso, type Period, type PeriodPreset } from "@/lib/periods";
import { cn } from "@/lib/utils";

export interface PeriodPickerProps {
  onChange: (period: Period) => void;
  defaultPreset?: PeriodPreset;
  /** ISO date used as "today"; defaults to the client clock. Injectable for tests. */
  today?: string;
  className?: string;
}

const SELECT_CLASS =
  "h-9 rounded-full border border-input bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export function PeriodPicker({ onChange, defaultPreset = "this_month", today, className }: PeriodPickerProps) {
  const anchor = today ?? todayIso();
  const [preset, setPreset] = useState<PeriodPreset>(defaultPreset);
  const [custom, setCustom] = useState({ from: anchor, to: anchor });
  const [customError, setCustomError] = useState<string | null>(null);

  const emit = (nextPreset: PeriodPreset, nextCustom = custom) => {
    try {
      onChange(resolvePeriod(nextPreset, anchor, nextCustom));
      setCustomError(null);
    } catch (error) {
      setCustomError(error instanceof Error ? error.message : "Invalid range");
    }
  };

  const handlePreset = (value: PeriodPreset) => {
    setPreset(value);
    emit(value);
  };

  const handleCustom = (field: "from" | "to", value: string) => {
    const next = { ...custom, [field]: value };
    setCustom(next);
    if (next.from && next.to) emit("custom", next);
  };

  return (
    <div className={cn("flex flex-wrap items-end gap-3", className)}>
      <div className="flex flex-col gap-1">
        <Label htmlFor="period-preset" className="text-xs text-muted">
          Period
        </Label>
        <select
          id="period-preset"
          className={SELECT_CLASS}
          value={preset}
          onChange={(event) => handlePreset(event.target.value as PeriodPreset)}
        >
          {PERIOD_PRESETS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      {preset === "custom" && (
        <>
          <div className="flex flex-col gap-1">
            <Label htmlFor="period-from" className="text-xs text-muted">
              From
            </Label>
            <Input id="period-from" type="date" value={custom.from} onChange={(e) => handleCustom("from", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="period-to" className="text-xs text-muted">
              To
            </Label>
            <Input id="period-to" type="date" value={custom.to} onChange={(e) => handleCustom("to", e.target.value)} />
          </div>
          {customError && (
            <p role="alert" className="text-xs text-danger">
              {customError}
            </p>
          )}
        </>
      )}
    </div>
  );
}
