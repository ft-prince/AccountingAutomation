"use client";

import { MoneyText } from "@/components/primitives/money-text";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { useConfirmRecurring, useRecurringPatterns } from "@/lib/forecast";
import { formatDate } from "@/lib/format";
import { toastApiError } from "@/lib/toast";

/** §8.2 recurring patterns: detected from history; the user confirms or dismisses each one inline. */
export function RecurringPanel({ canEdit }: { canEdit: boolean }) {
  const patterns = useRecurringPatterns();
  const confirm = useConfirmRecurring();
  const decide = (id: string, user_confirmed: boolean) =>
    confirm.mutate({ id, user_confirmed }, { onSuccess: () => toast({ title: user_confirmed ? "Pattern confirmed" : "Pattern dismissed" }), onError: (error) => toastApiError(error, "Could not update pattern") });

  return (
    <section id="recurring" aria-label="Recurring patterns" className="rounded-card border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold">Recurring patterns</h2>
      <p className="text-xs text-muted">Detected expenses; unconfirmed ones carry reduced weight in the engine until you decide.</p>
      <QueryState isPending={patterns.isPending} error={patterns.error} onRetry={() => void patterns.refetch()} skeletonClassName="mt-3 h-32 w-full">
        {patterns.data?.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No recurring patterns detected yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {patterns.data?.map((pattern) => (
              <li key={pattern.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span className="min-w-0">
                  <span className="block truncate font-medium">{pattern.party_name || pattern.category_name || "Recurring expense"}</span>
                  <span className="block text-xs text-muted tabular-nums">
                    every {pattern.period_days} d · next {formatDate(pattern.next_expected)} · {pattern.occurrences}× · confidence {pattern.confidence}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <MoneyText value={pattern.amount_p50 ?? "0"} className="font-medium" />
                  {pattern.user_confirmed === true && <StatusBadge status="confirmed" />}
                  {pattern.user_confirmed === false && <StatusBadge status="dismissed" tone="muted" />}
                  {pattern.user_confirmed === null || pattern.user_confirmed === undefined ? (
                    canEdit ? (
                      <>
                        <Button size="sm" variant="outline" disabled={confirm.isPending} onClick={() => decide(pattern.id, true)}>Confirm</Button>
                        <Button size="sm" variant="ghost" disabled={confirm.isPending} onClick={() => decide(pattern.id, false)}>Dismiss</Button>
                      </>
                    ) : (
                      <StatusBadge status="pending" label="unconfirmed" />
                    )
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  );
}
