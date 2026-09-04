"use client";

import Big from "big.js";
import { Check, EyeOff, Sparkles } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { EmptyState } from "@/components/primitives/empty-state";
import { MoneyText } from "@/components/primitives/money-text";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Landmark } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { useAutoMatch, useBankTransactions, useIgnoreTransaction, useMatchCandidates, useMatchTransaction, type AutoMatchResult, type MatchCandidate } from "@/lib/bank";
import { ICON_STROKE } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { orZero } from "@/lib/money";
import { toastApiError } from "@/lib/toast";
import type { BankTransaction } from "@/lib/types";
import { cn } from "@/lib/utils";
import { resolveMatchQueueKey } from "./match-queue-keys";

const SCORE_PCT = 100;

function isCredit(transaction: BankTransaction): boolean {
  return new Big(orZero(transaction.amount)).gt(0);
}

export function MatchQueue({ accountId }: { accountId: string }) {
  const transactions = useBankTransactions("unmatched", accountId);
  const rows = transactions.data?.results ?? [];
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [autoResult, setAutoResult] = useState<AutoMatchResult | null>(null);
  const selected = rows[selectedIndex] ?? null;
  const candidates = useMatchCandidates(selected?.id ?? null);
  const match = useMatchTransaction();
  const ignore = useIgnoreTransaction();
  const autoMatch = useAutoMatch();
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => setCandidateIndex(0), [selected?.id]);
  useEffect(() => {
    if (selectedIndex >= rows.length) setSelectedIndex(Math.max(0, rows.length - 1));
  }, [rows.length, selectedIndex]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${selectedIndex}"]`)?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const accept = useCallback(
    (candidate: MatchCandidate | undefined) => {
      if (!selected || !candidate || match.isPending) return;
      match.mutate(
        { id: selected.id, body: { invoices: candidate.invoices.map((invoice) => invoice.id) } },
        {
          onSuccess: () => toast({ title: "Matched", description: candidate.invoices.map((invoice) => invoice.invoice_number).join(", ") }),
          onError: (error) => toastApiError(error, "Match rejected"),
        },
      );
    },
    [selected, match],
  );

  const ignoreSelected = useCallback(() => {
    if (!selected || ignore.isPending) return;
    ignore.mutate({ id: selected.id }, { onSuccess: () => toast({ title: "Ignored" }), onError: (error) => toastApiError(error, "Could not ignore") });
  }, [selected, ignore]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const action = resolveMatchQueueKey({ key: event.key, metaKey: event.metaKey, ctrlKey: event.ctrlKey, altKey: event.altKey, target: event.target as HTMLElement | null });
      if (action === null) return;
      event.preventDefault();
      if (action === "next") setSelectedIndex((index) => Math.min(index + 1, Math.max(0, rows.length - 1)));
      else if (action === "previous") setSelectedIndex((index) => Math.max(index - 1, 0));
      else if (action === "accept") accept(candidates.data?.[candidateIndex]);
      else if (action === "ignore") ignoreSelected();
      else if (candidates.data && action.candidate < candidates.data.length) setCandidateIndex(action.candidate);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [rows.length, accept, ignoreSelected, candidates.data, candidateIndex]);

  const runAutoMatch = () =>
    autoMatch.mutate(accountId, {
      onSuccess: (result) => {
        setAutoResult(result);
        toast({ title: `Auto-match: ${result.matched} matched, ${result.proposed} proposed` });
      },
      onError: (error) => toastApiError(error, "Auto-match failed"),
    });

  return (
    <section aria-label="Match queue" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Match queue</h2>
          <p className="text-xs text-muted">
            <kbd className="rounded border border-border px-1">J</kbd>/<kbd className="rounded border border-border px-1">K</kbd> move · <kbd className="rounded border border-border px-1">1–9</kbd> pick candidate · <kbd className="rounded border border-border px-1">Enter</kbd>/<kbd className="rounded border border-border px-1">A</kbd> accept · <kbd className="rounded border border-border px-1">I</kbd> ignore
          </p>
        </div>
        <div className="flex items-center gap-3">
          {autoResult && (
            <span className="text-sm text-muted tabular-nums" role="status">
              Auto-match: {autoResult.matched} matched · {autoResult.proposed} proposed
            </span>
          )}
          <Button variant="outline" onClick={runAutoMatch} disabled={autoMatch.isPending || accountId === ""}>
            <Sparkles strokeWidth={ICON_STROKE} aria-hidden /> {autoMatch.isPending ? "Matching…" : "Auto-match"}
          </Button>
        </div>
      </div>

      <QueryState isPending={transactions.isPending} error={transactions.error} onRetry={() => transactions.refetch()} skeletonClassName="h-96 w-full">
        {rows.length === 0 ? (
          <EmptyState icon={Landmark} title="Nothing to match" description="Every imported transaction is matched or ignored. Import a statement to continue." />
        ) : (
          <div className="grid gap-3 lg:grid-cols-3">
            {/* Column 1 — unmatched transactions */}
            <ul ref={listRef} aria-label="Unmatched transactions" className="max-h-[32rem] divide-y divide-border overflow-auto rounded-card border border-border bg-surface">
              {rows.map((transaction, index) => (
                <li key={transaction.id} data-index={index}>
                  <button
                    type="button"
                    aria-current={index === selectedIndex}
                    onClick={() => setSelectedIndex(index)}
                    className={cn("flex w-full items-start justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-secondary", index === selectedIndex && "bg-secondary")}
                  >
                    <span className="min-w-0">
                      <span className="block truncate">{transaction.description || "—"}</span>
                      <span className="block text-xs text-muted tabular-nums">
                        {formatDate(transaction.date)} · {transaction.reference || "no ref"}
                      </span>
                    </span>
                    <MoneyText value={orZero(transaction.amount)} className={cn("shrink-0 font-medium", isCredit(transaction) ? "text-success" : "text-danger")} />
                  </button>
                </li>
              ))}
            </ul>

            {/* Column 2 — candidates for the selected transaction */}
            <div className="rounded-card border border-border bg-surface p-4">
              <h3 className="text-sm font-semibold">Candidates</h3>
              <QueryState isPending={candidates.isPending && selected !== null} error={candidates.error} onRetry={() => candidates.refetch()} skeletonClassName="mt-3 h-40 w-full">
                {candidates.data && candidates.data.length === 0 ? (
                  <p className="mt-3 text-sm text-muted">No invoices look like this transaction. Record a payment manually or ignore it.</p>
                ) : (
                  <ol className="mt-3 space-y-2" aria-label="Match candidates">
                    {(candidates.data ?? []).map((candidate, index) => (
                      <li key={index}>
                        <button
                          type="button"
                          aria-pressed={index === candidateIndex}
                          onClick={() => setCandidateIndex(index)}
                          onDoubleClick={() => accept(candidate)}
                          className={cn("w-full rounded-card border p-3 text-left text-sm", index === candidateIndex ? "border-accent" : "border-border hover:border-muted")}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">
                              <kbd className="mr-2 rounded border border-border px-1 text-xs">{index + 1}</kbd>
                              {candidate.invoices.map((invoice) => invoice.invoice_number).join(" + ")}
                            </span>
                            <span className="text-xs text-muted tabular-nums">{Math.round(candidate.score * SCORE_PCT)}%</span>
                          </div>
                          <p className="mt-1 text-xs text-muted">
                            {candidate.invoices[0]?.party} · <MoneyText value={candidate.amount} />
                          </p>
                          <ul className="mt-1 flex flex-wrap gap-1">
                            {candidate.reasons.map((reason) => (
                              <li key={reason} className="rounded-full border border-border px-2 py-0.5 text-xs text-muted">
                                {reason}
                              </li>
                            ))}
                          </ul>
                        </button>
                      </li>
                    ))}
                  </ol>
                )}
              </QueryState>
            </div>

            {/* Column 3 — transaction detail + actions */}
            <div className="rounded-card border border-border bg-surface p-4">
              {selected && (
                <>
                  <h3 className="text-sm font-semibold">Transaction</h3>
                  <dl className="mt-3 space-y-1.5 text-sm">
                    <div className="flex justify-between gap-3"><dt className="text-muted">Date</dt><dd className="tabular-nums">{formatDate(selected.date)}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-muted">Amount</dt><dd><MoneyText value={orZero(selected.amount)} className={isCredit(selected) ? "text-success" : "text-danger"} /></dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-muted">Balance after</dt><dd>{selected.balance_after ? <MoneyText value={selected.balance_after} /> : "—"}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-muted">Reference</dt><dd className="font-mono text-xs">{selected.reference || "—"}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-muted">Status</dt><dd><StatusBadge status={selected.match_status} /></dd></div>
                  </dl>
                  <p className="mt-3 break-words text-sm">{selected.description || "—"}</p>
                  <div className="mt-4 flex flex-col gap-2">
                    <Button onClick={() => accept(candidates.data?.[candidateIndex])} disabled={!candidates.data?.[candidateIndex] || match.isPending}>
                      <Check strokeWidth={ICON_STROKE} aria-hidden /> Accept candidate {candidateIndex + 1}
                    </Button>
                    <Button variant="outline" onClick={ignoreSelected} disabled={ignore.isPending}>
                      <EyeOff strokeWidth={ICON_STROKE} aria-hidden /> Ignore
                    </Button>
                    <Button variant="ghost" asChild>
                      <Link href="/payments">Record payment manually</Link>
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </QueryState>
    </section>
  );
}
