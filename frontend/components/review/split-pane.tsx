"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useSplitPane } from "./use-split-pane";

export const SPLIT_STORAGE_KEY = "review.split-ratio";
const PERCENT = 100;

export interface SplitPaneProps {
  left: ReactNode;
  right: ReactNode;
  className?: string;
}

/** PDF left, form right; the divider drags and the ratio survives reloads. */
export function SplitPane({ left, right, className }: SplitPaneProps) {
  const { containerRef, ratio, isDragging, handleProps } = useSplitPane(SPLIT_STORAGE_KEY);
  return (
    <div ref={containerRef} className={cn("flex min-h-0 flex-1 overflow-hidden rounded-card border border-border bg-surface", isDragging && "select-none", className)}>
      <div className="min-h-0 min-w-0 overflow-hidden" style={{ width: `${ratio * PERCENT}%` }}>
        {left}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panes"
        aria-valuenow={Math.round(ratio * PERCENT)}
        className={cn("w-1.5 shrink-0 cursor-col-resize bg-border transition-colors hover:bg-accent", isDragging && "bg-accent")}
        {...handleProps}
      />
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">{right}</div>
    </div>
  );
}
