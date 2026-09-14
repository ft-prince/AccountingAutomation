"use client";

import { Check, ChevronDown, ChevronUp, Copy, HelpCircle, X } from "lucide-react";
import { MoneyText } from "@/components/primitives/money-text";
import { Button } from "@/components/ui/button";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { formatClock, formatIsoDate } from "./format";

export type SaveStatus = { kind: "clean" } | { kind: "dirty" } | { kind: "saving" } | { kind: "saved"; at: Date };

export interface QueueHeaderProps {
  position: number;
  total: number;
  remaining: number;
  invoice: { invoice_number: string; party_name: string; invoice_date: string; total?: string; confidence?: string; confidence_field?: string | null } | null;
  saveStatus: SaveStatus;
  canConfirm: boolean;
  isBusy: boolean;
  onConfirm: () => void;
  onReject: () => void;
  onDuplicate: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onHelp: () => void;
}

const PERCENT = 100;

function saveLabel(status: SaveStatus): string {
  switch (status.kind) {
    case "clean":
      return "";
    case "dirty":
      return "Unsaved changes";
    case "saving":
      return "Saving…";
    case "saved":
      return `Saved · ${formatClock(status.at)}`;
  }
}

/** Queue position, progress bar, the invoice at a glance, and the three decisions. */
export function QueueHeader({ position, total, remaining, invoice, saveStatus, canConfirm, isBusy, onConfirm, onReject, onDuplicate, onPrevious, onNext, onHelp }: QueueHeaderProps) {
  const done = total - remaining;
  const progress = total === 0 ? 0 : Math.round((done / total) * PERCENT);
  return (
    <header className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            Review <span className="font-display italic">queue</span>.
          </h1>
          <span className="text-sm text-muted tabular-nums" data-testid="queue-position">
            {total === 0 ? "Nothing waiting" : `${position} of ${total} · ${remaining} remaining`}
          </span>
          <div className="flex items-center">
            <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Previous invoice (K)" onClick={onPrevious} disabled={isBusy}>
              <ChevronUp size={ICON_SIZE} strokeWidth={ICON_STROKE} className="text-muted" />
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Next invoice (J)" onClick={onNext} disabled={isBusy}>
              <ChevronDown size={ICON_SIZE} strokeWidth={ICON_STROKE} className="text-muted" />
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span role="status" aria-live="polite" className={cn("text-xs tabular-nums", saveStatus.kind === "dirty" ? "text-warning" : "text-muted")}>
            {saveLabel(saveStatus)}
          </span>
          <Button variant="outline" size="sm" onClick={onReject} disabled={isBusy || !invoice}>
            <X /> Reject <kbd className="ml-1 text-muted">R</kbd>
          </Button>
          <Button variant="outline" size="sm" onClick={onDuplicate} disabled={isBusy || !invoice}>
            <Copy /> Duplicate <kbd className="ml-1 text-muted">D</kbd>
          </Button>
          {canConfirm && (
            <Button size="sm" onClick={onConfirm} disabled={isBusy || !invoice}>
              <Check /> Confirm <kbd className="ml-1 opacity-80">⏎</kbd>
            </Button>
          )}
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Keyboard shortcuts (?)" onClick={onHelp}>
            <HelpCircle size={ICON_SIZE} strokeWidth={ICON_STROKE} className="text-muted" />
          </Button>
        </div>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-border" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Queue progress">
        <div className="h-full bg-accent transition-[width] duration-150" style={{ width: `${progress}%` }} />
      </div>
      {invoice && (
        <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
          <span className="font-medium text-foreground">{invoice.invoice_number}</span>
          <span>{invoice.party_name}</span>
          <span>{formatIsoDate(invoice.invoice_date)}</span>
          {invoice.total !== undefined && <MoneyText value={invoice.total} />}
          {invoice.confidence !== undefined && (
            <span className="tabular-nums">
              confidence {invoice.confidence}
              {invoice.confidence_field && <span className="text-muted"> · weakest {invoice.confidence_field}</span>}
            </span>
          )}
        </p>
      )}
    </header>
  );
}
