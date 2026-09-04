"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useUser } from "@/lib/auth";
import { ICON_STROKE } from "@/lib/constants";
import { useDraft, useGenerateDraft, useThread, useThreadAction } from "@/lib/mail";
import { canReview } from "@/lib/mail-review";
import { toastApiError } from "@/lib/toast";
import { DraftPanel } from "./draft-panel";
import { MessageList } from "./message-list";
import { PartyCard } from "./party-card";
import { IntentChip, PriorityChip, SlaChip, useNow } from "./thread-chips";

const DEFAULT_SNOOZE_HOURS = 24;

function defaultSnoozeIso(): string {
  const until = new Date(Date.now() + DEFAULT_SNOOZE_HOURS * 60 * 60 * 1000);
  until.setSeconds(0, 0);
  return until.toISOString().slice(0, 16);
}

/** §11 /inbox/[thread] — inbound left, party card + draft right. */
export function ThreadView({ id, now: fixedNow }: { id: string; now?: string }) {
  const now = useNow(fixedNow);
  const { data: me } = useUser();
  const thread = useThread(id);
  const latestSummary = thread.data?.drafts.find((draft) => draft.status !== "superseded") ?? thread.data?.drafts[0];
  const draft = useDraft(latestSummary?.id);
  const threadAction = useThreadAction(id);
  const generate = useGenerateDraft(id);
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const [snoozeUntil, setSnoozeUntil] = useState(defaultSnoozeIso);
  const isReviewer = canReview(me?.role);

  const runThread = (input: Parameters<typeof threadAction.mutate>[0], success: string) =>
    threadAction.mutate(input, { onSuccess: () => { toast({ title: success }); setSnoozeOpen(false); }, onError: (error) => toastApiError(error, "Action failed") });

  return (
    <div className="space-y-5">
      <Link href="/inbox" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground">
        <ArrowLeft size={14} strokeWidth={ICON_STROKE} aria-hidden /> Inbox
      </Link>
      <QueryState isPending={thread.isPending} error={thread.error} onRetry={() => void thread.refetch()} skeletonClassName="h-96 w-full">
        {thread.data && (
          <>
            <PageHeader
              title={thread.data.subject || "(no subject)"}
              description={
                <span className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={thread.data.status} tone={thread.data.status === "awaiting_review" ? "warning" : thread.data.status === "replied" ? "success" : "muted"} />
                  <PriorityChip priority={thread.data.priority} />
                  <IntentChip intent={thread.data.intent} />
                  {thread.data.sentiment && <span>sentiment {thread.data.sentiment}</span>}
                  <SlaChip slaDueAt={thread.data.sla_due_at} now={now} />
                </span>
              }
              actions={
                isReviewer && (
                  <>
                    <Button variant="outline" onClick={() => setSnoozeOpen(true)} disabled={threadAction.isPending}>Snooze</Button>
                    <Button variant="outline" onClick={() => runThread({ kind: "close" }, "Thread closed")} disabled={threadAction.isPending}>Close</Button>
                    <Button variant="ghost" onClick={() => runThread({ kind: "ignore" }, "Thread ignored")} disabled={threadAction.isPending}>Ignore</Button>
                  </>
                )
              }
            />
            <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <MessageList messages={thread.data.messages} />
              <div className="space-y-4">
                <PartyCard partyId={thread.data.party} partyName={thread.data.party_name} />
                {latestSummary ? (
                  <QueryState isPending={draft.isPending} error={draft.error} onRetry={() => void draft.refetch()} skeletonClassName="h-80 w-full">
                    {draft.data && <DraftPanel key={draft.data.id} draft={draft.data} threadId={id} role={me?.role} />}
                  </QueryState>
                ) : (
                  <section aria-label="Draft" className="rounded-card border border-dashed border-border p-4 text-sm">
                    <p className="text-muted">No draft yet.</p>
                    {isReviewer && (
                      <Button className="mt-3" onClick={() => generate.mutate(undefined, { onSuccess: () => toast({ title: "Draft generated" }), onError: (error) => toastApiError(error, "Could not draft") })} disabled={generate.isPending}>
                        {generate.isPending ? "Drafting…" : "Generate draft"}
                      </Button>
                    )}
                  </section>
                )}
              </div>
            </div>
          </>
        )}
      </QueryState>
      <ConfirmDialog open={snoozeOpen} onOpenChange={setSnoozeOpen} title="Snooze thread" description="Hidden from the review queue until this time." confirmLabel="Snooze" isPending={threadAction.isPending} onConfirm={() => runThread({ kind: "snooze", until: new Date(snoozeUntil).toISOString() }, "Snoozed")}>
        <Input aria-label="Snooze until" type="datetime-local" value={snoozeUntil} onChange={(event) => setSnoozeUntil(event.target.value)} />
      </ConfirmDialog>
    </div>
  );
}
