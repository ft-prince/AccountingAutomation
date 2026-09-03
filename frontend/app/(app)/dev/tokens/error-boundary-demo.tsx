"use client";

import { useState } from "react";
import { ErrorBoundary } from "@/components/primitives/error-boundary";
import { Button } from "@/components/ui/button";

function Exploder({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("Sample render failure from /dev/tokens");
  return <p className="text-sm text-muted">Healthy child component.</p>;
}

export function ErrorBoundaryDemo() {
  const [shouldThrow, setShouldThrow] = useState(false);
  return (
    <div className="space-y-3">
      <ErrorBoundary>
        <Exploder shouldThrow={shouldThrow} />
      </ErrorBoundary>
      <Button variant="outline" size="sm" onClick={() => setShouldThrow(true)}>
        Trigger error
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setShouldThrow(false)}>
        Heal child
      </Button>
    </div>
  );
}
