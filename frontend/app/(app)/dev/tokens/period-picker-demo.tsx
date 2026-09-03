"use client";

import { useState } from "react";
import { PeriodPicker } from "@/components/primitives/period-picker";
import type { Period } from "@/lib/periods";

export function PeriodPickerDemo() {
  const [period, setPeriod] = useState<Period | null>(null);
  return (
    <div className="space-y-2">
      <PeriodPicker onChange={setPeriod} />
      <pre className="rounded-md border border-border bg-background p-3 font-mono text-xs text-muted">
        {period ? JSON.stringify(period, null, 2) : "Pick a period to see the emitted value"}
      </pre>
    </div>
  );
}
