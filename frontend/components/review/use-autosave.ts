"use client";

import { useEffect, useRef } from "react";

export const AUTOSAVE_INTERVAL_MS = 5_000;

interface AutosaveOptions {
  isDirty: boolean;
  isInFlight: boolean;
  save: () => void;
  intervalMs?: number;
}

/** Calls `save` every interval while dirty and idle; flushes once on unmount. */
export function useAutosave({ isDirty, isInFlight, save, intervalMs = AUTOSAVE_INTERVAL_MS }: AutosaveOptions): void {
  const latest = useRef({ isDirty, isInFlight, save });
  latest.current = { isDirty, isInFlight, save };

  useEffect(() => {
    const timer = window.setInterval(() => {
      const { isDirty: dirty, isInFlight: inFlight, save: run } = latest.current;
      if (dirty && !inFlight) run();
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);

  useEffect(() => {
    return () => {
      const { isDirty: dirty, isInFlight: inFlight, save: run } = latest.current;
      if (dirty && !inFlight) run();
    };
  }, []);
}
