"use client";

import { Building2 } from "lucide-react";
import { MoneyText } from "@/components/primitives/money-text";
import { Skeleton } from "@/components/ui/skeleton";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";
import { type AgingRow, useAging, useParty, type ValidationIssue } from "@/lib/invoices";
import { cn } from "@/lib/utils";
import { IssueList } from "./issue-list";

const AGING_BUCKETS = ["0-30", "31-60", "61-90", "90+"] as const;
const OVERDUE_BUCKET = "90+";
const ZERO = "0";

export interface PartyCardProps {
  partyId: string;
  partyName: string;
  direction: "inward" | "outward";
  issues: readonly ValidationIssue[];
  onResolve: (issueId: string, note: string) => void;
  isReadOnly: boolean;
}

function isNonZero(amount: string): boolean {
  return /[1-9]/.test(amount);
}

/** Who we are dealing with: identity, open balance from the aging report, and a risk-band slot for Phase 18. */
export function PartyCard({ partyId, partyName, direction, issues, onResolve, isReadOnly }: PartyCardProps) {
  const party = useParty(partyId);
  const aging = useAging(direction === "inward" ? "ap" : "ar");
  const row: AgingRow | undefined = aging.data?.rows.find((candidate) => candidate.party === partyId);
  const name = party.data?.display_name || party.data?.legal_name || partyName;

  return (
    <section aria-label="Party" className="rounded-card border border-border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Building2 size={ICON_SIZE} strokeWidth={ICON_STROKE} className="shrink-0 text-muted" aria-hidden />
            <h3 className="truncate font-semibold">{name}</h3>
          </div>
          {party.isPending ? (
            <Skeleton className="mt-1 h-4 w-40" />
          ) : (
            <p className="mt-1 text-xs text-muted">
              {party.data?.gstin ? `GSTIN ${party.data.gstin}` : "No GSTIN"}
              {party.data?.state_code ? ` · State ${party.data.state_code}` : ""}
              {party.data?.payment_terms_days !== undefined ? ` · Net ${party.data.payment_terms_days}` : ""}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-xs text-muted">{direction === "inward" ? "Open payable" : "Open receivable"}</p>
          {aging.isPending ? <Skeleton className="mt-1 h-5 w-24" /> : <MoneyText value={row?.total ?? ZERO} className="font-semibold" />}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
        {AGING_BUCKETS.map((bucket) => {
          const amount = row?.[bucket] ?? ZERO;
          const isOverdue = bucket === OVERDUE_BUCKET && isNonZero(amount);
          return (
            <span key={bucket} className={cn("inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 tabular-nums", isOverdue ? "border-warning text-warning" : "text-muted")}>
              {bucket}d <MoneyText value={amount} abbreviate />
            </span>
          );
        })}
        <span className="inline-flex items-center rounded-full border border-dashed border-border px-2 py-0.5 text-muted" title="Customer risk bands ship with the forecasting UI (Phase 18).">
          Risk band · Phase 18
        </span>
      </div>
      <IssueList issues={issues} onResolve={onResolve} isReadOnly={isReadOnly} className="mt-2" />
    </section>
  );
}
