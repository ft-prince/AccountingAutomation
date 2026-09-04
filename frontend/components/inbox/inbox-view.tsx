"use client";

import { Inbox, MailPlus } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/primitives/empty-state";
import { MoneyText } from "@/components/primitives/money-text";
import { NativeSelect } from "@/components/primitives/native-select";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { isTypingTarget } from "@/lib/keyboard";
import { useMailboxes, useThreads } from "@/lib/mail";
import { resolvePeriod, todayIso } from "@/lib/periods";
import { useReport } from "@/lib/reports";
import type { Intent, ThreadStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { IntentChip, PriorityChip, SlaChip, useNow } from "./thread-chips";

const STATUSES: readonly ThreadStatus[] = ["new", "drafted", "awaiting_review", "replied", "closed", "ignored"];
const INTENTS: readonly Intent[] = ["invoice_query", "payment_confirmation", "payment_delay_notice", "statement_request", "quote_request", "po_or_order", "dispute", "vendor_bill_received", "support", "meeting_or_scheduling", "newsletter_or_spam", "other"];
const CONNECT_HREF = "/settings?tab=mail";

/** §11 /inbox — thread list ordered by the API (sla_due_at, then priority). J/K move, Enter opens. */
export function InboxView({ now: fixedNow }: { now?: string }) {
  const router = useRouter();
  const search = useSearchParams();
  const now = useNow(fixedNow);
  const [status, setStatus] = useState<ThreadStatus | "">("");
  const [intent, setIntent] = useState<Intent | "">("");
  const [cursor, setCursor] = useState(0);
  const party = search.get("party") ?? undefined;

  const mailboxes = useMailboxes();
  const hasMailbox = (mailboxes.data ?? []).some((mailbox) => mailbox.status !== "revoked");
  const threads = useThreads({ status, intent, party }, mailboxes.isSuccess && hasMailbox);
  const period = resolvePeriod("fy_to_date", todayIso());
  const arAging = useReport("ar-aging", { from: period.from, to: period.to, basis: "accrual" }, hasMailbox);
  const balances = useMemo(() => new Map((arAging.data?.rows ?? []).map((row) => [row.party, row.total])), [arAging.data]);

  const rows = useMemo(() => threads.data?.results ?? [], [threads.data]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "j") setCursor((index) => Math.min(index + 1, Math.max(rows.length - 1, 0)));
      else if (key === "k") setCursor((index) => Math.max(index - 1, 0));
      else if (event.key === "Enter" && rows[cursor]) router.push(`/inbox/${rows[cursor].id}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, cursor, router]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox,"
        emphasis="reviewed"
        description="Every reply is drafted for a human; nothing is sent without one."
        actions={
          <>
            <NativeSelect aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value as ThreadStatus | ""); setCursor(0); }}>
              <option value="">All statuses</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
              ))}
            </NativeSelect>
            <NativeSelect aria-label="Intent" value={intent} onChange={(event) => { setIntent(event.target.value as Intent | ""); setCursor(0); }}>
              <option value="">All intents</option>
              {INTENTS.map((value) => (
                <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
              ))}
            </NativeSelect>
          </>
        }
      />

      <QueryState isPending={mailboxes.isPending} error={mailboxes.error} onRetry={() => void mailboxes.refetch()} skeletonClassName="h-64 w-full">
        {!hasMailbox ? (
          <EmptyState
            icon={MailPlus}
            title="No mailbox connected"
            description="Connect Gmail or Microsoft 365 to start classifying client email and drafting replies for review."
            action={
              <Button asChild>
                <Link href={CONNECT_HREF}>Connect a mailbox</Link>
              </Button>
            }
          />
        ) : (
          <QueryState isPending={threads.isPending} error={threads.error} onRetry={() => void threads.refetch()} skeletonClassName="h-64 w-full">
            {rows.length === 0 ? (
              <EmptyState icon={Inbox} title="Nothing to review" description="New threads appear here after the next sync." />
            ) : (
              <ol className="divide-y divide-border rounded-card border border-border bg-surface" aria-label="Threads">
                {rows.map((thread, index) => {
                  const balance = thread.party ? balances.get(thread.party) : undefined;
                  return (
                    <li key={thread.id} data-selected={index === cursor} className={cn("transition-colors", index === cursor && "bg-secondary")}>
                      <Link href={`/inbox/${thread.id}`} className="grid gap-2 px-4 py-3 md:grid-cols-[1fr_auto] md:items-center" onMouseEnter={() => setCursor(index)}>
                        <span className="min-w-0">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="truncate text-sm font-medium">{thread.subject || "(no subject)"}</span>
                            <PriorityChip priority={thread.priority} />
                            <IntentChip intent={thread.intent} />
                            {thread.requires_finance_data && <StatusBadge status="finance" tone="info" label="needs finance data" />}
                          </span>
                          <span className="mt-1 block text-xs text-muted">
                            {thread.party_name || "Unresolved party"}
                            {balance !== undefined && (
                              <>
                                {" · open "}
                                <MoneyText value={balance} />
                              </>
                            )}
                            {thread.last_inbound_at && ` · last inbound ${formatDate(thread.last_inbound_at)}`}
                          </span>
                        </span>
                        <span className="flex items-center gap-2 md:justify-end">
                          <StatusBadge status={thread.status} tone={thread.status === "awaiting_review" ? "warning" : thread.status === "replied" ? "success" : "muted"} />
                          <SlaChip slaDueAt={thread.sla_due_at} now={now} />
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            )}
            <p className="mt-2 text-xs text-muted">J / K to move · Enter to open</p>
          </QueryState>
        )}
      </QueryState>
    </div>
  );
}
