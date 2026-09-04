"use client";

import { Check, FileText, Paperclip, RefreshCw } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useDraftAction, useGenerateDraft } from "@/lib/mail";
import { acknowledgedFlags, canApproveDraft, canReview, canSendDraft, unacknowledgedFlags } from "@/lib/mail-review";
import { toastApiError } from "@/lib/toast";
import type { Draft } from "@/lib/types";
import { cn } from "@/lib/utils";
import { WordDiff } from "./word-diff";

const TEXTAREA_CLASS = "min-h-[16rem] w-full rounded-card border border-input bg-surface p-3 text-sm leading-6 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-60";
const REJECT_REASON_MIN = 3;

interface AttachmentLike {
  filename?: string;
  name?: string;
  kind?: string;
}

function proposedAttachments(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry) => (typeof entry === "string" ? entry : ((entry as AttachmentLike).filename ?? (entry as AttachmentLike).name ?? (entry as AttachmentLike).kind ?? "attachment")));
}

function FlagChips({ draft, onAcknowledge, isPending, canAcknowledge }: { draft: Draft; onAcknowledge: (flag: string) => void; isPending: boolean; canAcknowledge: boolean }) {
  const acked = new Set(acknowledgedFlags(draft.acknowledged_flags).map((entry) => entry.flag));
  if (draft.guardrail_flags.length === 0) return <p className="text-xs text-success">No guardrail flags raised.</p>;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Guardrail flags">
      {draft.guardrail_flags.map((flag) => {
        const isAcked = acked.has(flag);
        return (
          <li key={flag}>
            <button
              type="button"
              data-flag={flag}
              data-acknowledged={isAcked}
              disabled={isAcked || isPending || !canAcknowledge}
              onClick={() => onAcknowledge(flag)}
              aria-pressed={isAcked}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                isAcked ? "border-success text-success" : "border-warning text-warning hover:bg-secondary",
                "disabled:cursor-default",
              )}
              title={isAcked ? "Acknowledged" : "Click to acknowledge this flag"}
            >
              {isAcked && <Check size={12} strokeWidth={2} aria-hidden />}
              {flag.replace(/_/g, " ")}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export interface DraftPanelProps {
  draft: Draft;
  threadId: string;
  role: string | null | undefined;
}

/**
 * §6.6 review actions. Approve/Send render ONLY when every guardrail flag is acknowledged and the
 * role may review — both gates are evaluated here and tested in draft-panel.test.tsx.
 */
export function DraftPanel({ draft, threadId, role }: DraftPanelProps) {
  const action = useDraftAction(draft.id);
  const regenerate = useGenerateDraft(threadId);
  const [body, setBody] = useState(draft.body_text);
  const [instruction, setInstruction] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [contextOpen, setContextOpen] = useState(false);

  const pending = unacknowledgedFlags(draft);
  const isReviewer = canReview(role);
  const isEditable = isReviewer && draft.status === "pending_review";
  const isDirty = body !== draft.body_text;
  const showApprove = canApproveDraft(role, draft) && !isDirty;
  const showSend = canSendDraft(role, draft);
  const attachments = proposedAttachments(draft.proposed_attachments);
  const sentText = draft.status === "sent" ? draft.body_text : null;
  const originalText = draft.revisions.length > 0 ? (draft.revisions[0].before ?? draft.body_text) : draft.body_text;

  const run = (input: Parameters<typeof action.mutate>[0], success: string) =>
    action.mutate(input, { onSuccess: () => toast({ title: success }), onError: (error) => toastApiError(error, "Action failed") });

  const approveAndSend = () =>
    action.mutate({ kind: "approve" }, {
      onSuccess: () => action.mutate({ kind: "send" }, { onSuccess: () => toast({ title: "Queued for sending" }), onError: (error) => toastApiError(error, "Send refused") }),
      onError: (error) => toastApiError(error, "Approve refused"),
    });

  return (
    <section aria-label="Draft" className="space-y-4 rounded-card border border-border bg-surface p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Draft v{draft.version}</h2>
          <StatusBadge status={draft.status} tone={draft.status === "sent" ? "success" : draft.status.endsWith("approved") ? "info" : draft.status === "rejected" ? "danger" : "warning"} />
          <span className="text-xs text-muted tabular-nums">confidence {draft.confidence} · {draft.tone || "tone n/a"}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setContextOpen(true)}>
          <FileText strokeWidth={ICON_STROKE} aria-hidden /> Context snapshot
        </Button>
      </header>

      <FlagChips draft={draft} onAcknowledge={(flag) => run({ kind: "acknowledge-flag", flag }, `Acknowledged ${flag.replace(/_/g, " ")}`)} isPending={action.isPending} canAcknowledge={isReviewer} />
      {pending.length > 0 && (
        <p role="status" className="text-xs text-warning">
          {pending.length} flag{pending.length === 1 ? "" : "s"} must be acknowledged before this draft can be approved.
        </p>
      )}

      {sentText !== null ? (
        <div className="space-y-2">
          <p className="text-xs text-muted">Sent {draft.sent_at ? new Date(draft.sent_at).toLocaleString("en-IN") : ""} · edit distance {draft.edit_distance ?? "—"}</p>
          <WordDiff before={originalText} after={sentText} className="rounded-card border border-border p-3" />
        </div>
      ) : (
        <textarea aria-label="Draft body" className={TEXTAREA_CLASS} value={body} onChange={(event) => setBody(event.target.value)} disabled={!isEditable || action.isPending} />
      )}

      {attachments.length > 0 && (
        <ul className="flex flex-wrap gap-2 text-xs text-muted" aria-label="Proposed attachments">
          {attachments.map((name) => (
            <li key={name} className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5">
              <Paperclip size={12} strokeWidth={ICON_STROKE} aria-hidden /> {name} <span className="opacity-70">· attached on approval</span>
            </li>
          ))}
        </ul>
      )}

      {isReviewer && draft.status !== "sent" && draft.status !== "superseded" && (
        <div className="flex flex-wrap items-center gap-2">
          {isDirty && (
            <Button variant="outline" onClick={() => run({ kind: "edit", body_text: body }, "Draft updated")} disabled={action.isPending}>
              Save edit
            </Button>
          )}
          {showApprove && (
            <Button onClick={approveAndSend} disabled={action.isPending}>
              Approve & send
            </Button>
          )}
          {showSend && draft.status !== "pending_review" && (
            <Button onClick={() => run({ kind: "send" }, "Queued for sending")} disabled={action.isPending}>
              Send
            </Button>
          )}
          {draft.status === "pending_review" && (
            <Button variant="outline" onClick={() => setRejectOpen(true)} disabled={action.isPending}>
              Reject
            </Button>
          )}
        </div>
      )}

      {isReviewer && (
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            regenerate.mutate(instruction || undefined, {
              onSuccess: () => { toast({ title: "New draft version generated" }); setInstruction(""); },
              onError: (error) => toastApiError(error, "Could not regenerate"),
            });
          }}
        >
          <Input aria-label="Regenerate instruction" placeholder="Regenerate with an instruction, e.g. 'shorter, ask for the PO number'" value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          <Button type="submit" variant="outline" disabled={regenerate.isPending}>
            <RefreshCw strokeWidth={ICON_STROKE} className={cn(regenerate.isPending && "animate-spin")} aria-hidden /> Regenerate
          </Button>
        </form>
      )}

      <ConfirmDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        title="Reject this draft"
        description="The reason feeds the few-shot pool once a second reviewer marks it a good example (§6.6)."
        confirmLabel="Reject"
        destructive
        isPending={action.isPending}
        onConfirm={() => {
          if (reason.trim().length < REJECT_REASON_MIN) return;
          action.mutate({ kind: "reject", reason: reason.trim() }, { onSuccess: () => { toast({ title: "Draft rejected" }); setRejectOpen(false); }, onError: (error) => toastApiError(error, "Reject failed") });
        }}
      >
        <Input aria-label="Rejection reason" placeholder="Reason (required)" value={reason} onChange={(event) => setReason(event.target.value)} />
      </ConfirmDialog>

      <Sheet open={contextOpen} onOpenChange={setContextOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>Context snapshot</SheetTitle>
            <SheetDescription>Everything the model was allowed to see (§6.5). Amounts, dates and invoice numbers in the draft must come from here.</SheetDescription>
          </SheetHeader>
          <pre className="mt-4 whitespace-pre-wrap rounded-card border border-border bg-background p-3 font-mono text-xs">{JSON.stringify(draft.context_snapshot ?? {}, null, 2)}</pre>
        </SheetContent>
      </Sheet>
    </section>
  );
}
