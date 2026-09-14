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
    // Below lg the panes stack: document on top at a fixed height, form scrolling under it.
    <div ref={containerRef} className={cn("flex min-h-0 flex-1 flex-col overflow-hidden rounded-card border border-border bg-surface lg:flex-row", isDragging && "select-none", className)}>
      <div className="h-[40vh] min-h-0 w-full min-w-0 shrink-0 overflow-hidden border-b border-border lg:h-auto lg:w-[var(--split)] lg:border-b-0" style={{ "--split": `${ratio * PERCENT}%` } as React.CSSProperties}>
        {left}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panes"
        aria-valuenow={Math.round(ratio * PERCENT)}
        className={cn("hidden w-1.5 shrink-0 cursor-col-resize bg-border transition-colors hover:bg-accent lg:block", isDragging && "bg-accent")}
        {...handleProps}
      />
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">{right}</div>
    </div>
  );
}
