"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

const MIN_RATIO = 0.25;
const MAX_RATIO = 0.75;
const DEFAULT_RATIO = 0.5;

function readStored(key: string): number {
  if (typeof window === "undefined") return DEFAULT_RATIO;
  const raw = window.localStorage.getItem(key);
  const parsed = raw === null ? Number.NaN : Number(raw);
  return Number.isFinite(parsed) ? clamp(parsed) : DEFAULT_RATIO;
}

function clamp(ratio: number): number {
  return Math.min(MAX_RATIO, Math.max(MIN_RATIO, ratio));
}

/** Draggable split (pointer events), ratio persisted in localStorage. */
export function useSplitPane(storageKey: string) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [ratio, setRatio] = useState(DEFAULT_RATIO);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    setRatio(readStored(storageKey));
  }, [storageKey]);

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsDragging(true);
  }, []);

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      if (rect.width === 0) return;
      setRatio(clamp((event.clientX - rect.left) / rect.width));
    },
    [isDragging],
  );

  const onPointerUp = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      if (!isDragging) return;
      event.currentTarget.releasePointerCapture(event.pointerId);
      setIsDragging(false);
      window.localStorage.setItem(storageKey, String(ratio));
    },
    [isDragging, ratio, storageKey],
  );

  return { containerRef, ratio, isDragging, handleProps: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp } };
}
