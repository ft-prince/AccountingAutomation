"use client";

import { Inbox, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { EmptyState } from "@/components/primitives/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useUser } from "@/lib/auth";
import { CONFIRM_ROLES, type InvoiceDetail, useInvoice, useResolveIssue, useUpdateInvoice } from "@/lib/invoices";
import { resolveShortcut, type ShortcutAction } from "@/lib/keyboard";
import { toastApiError } from "@/lib/toast";
import { fieldSelector, firstFocusTarget, isLowConfidence } from "./confidence";
import { ConfirmGateDialog } from "./confirm-gate-dialog";
import { DuplicateDialog } from "./duplicate-dialog";
import { EMPTY_FORM_STATE, formReducer, isDirty, toPatch } from "./form-state";
import { InvoiceForm } from "./invoice-form";
import { issuesAt } from "./issue-map";
import { LineTable } from "./line-table";
import { PartyCard } from "./party-card";
import { PdfPane } from "./pdf-pane";
import { QueueHeader, type SaveStatus } from "./queue-header";
import { computeInvoice } from "./recompute";
import { RejectDialog } from "./reject-dialog";
import { ShortcutOverlay } from "./shortcut-overlay";
import { SplitPane } from "./split-pane";
import { TotalsPanel, totalsFromInvoice } from "./totals-panel";
import { useAutosave } from "./use-autosave";
import { useReviewActions } from "./use-review-actions";
import { useReviewQueueState } from "./use-review-queue";

type Overlay = "reject" | "duplicate" | "help" | null;

const VIEWER_ROLE = "viewer";

function documentIdOf(invoice: InvoiceDetail): string | null {
  return invoice.document || null;
}

/** /review — PDF left, form right, keyboard-first (PROJECT_SPECS §11). */
export function ReviewScreen() {
  const { data: me } = useUser();
  const role = me?.role ?? null;
  const canConfirm = role !== null && CONFIRM_ROLES.includes(role);
  const isReadOnly = role === null || role === VIEWER_ROLE;

  const queue = useReviewQueueState();
  const detail = useInvoice(queue.currentId);
  const invoice = detail.data && detail.data.id === queue.currentId ? detail.data : null;

  const [form, dispatchForm] = useReducer(formReducer, EMPTY_FORM_STATE);
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const formRef = useRef<HTMLDivElement>(null);
  const update = useUpdateInvoice();
  const resolveIssue = useResolveIssue();

  const isFormForInvoice = invoice !== null && form.invoiceId === invoice.id;
  const dirty = isFormForInvoice && isDirty(form);

  useEffect(() => {
    if (invoice && form.invoiceId !== invoice.id) {
      dispatchForm({ type: "reset", invoice });
      setSavedAt(null);
    }
  }, [invoice, form.invoiceId]);

  // Focus the first low-confidence field once the form for this invoice is on screen.
  const focusRef = useRef<{ invoiceConfidence?: string; lineConfidences: (string | undefined)[] }>({ lineConfidences: [] });
  focusRef.current = { invoiceConfidence: invoice?.confidence, lineConfidences: form.draft.lines.map((line) => line.confidence) };
  useEffect(() => {
    if (!form.invoiceId) return;
    const target = firstFocusTarget(focusRef.current.invoiceConfidence, focusRef.current.lineConfidences);
    const element = formRef.current?.querySelector<HTMLElement>(fieldSelector(target));
    element?.focus();
    if (element instanceof HTMLInputElement) element.select();
  }, [form.invoiceId]);

  const save = useCallback(async (): Promise<boolean> => {
    if (!form.invoiceId || !isDirty(form) || isReadOnly) return true;
    const sentPatch = toPatch(form.draft);
    try {
      const saved = await update.mutateAsync({ id: form.invoiceId, patch: sentPatch });
      dispatchForm({ type: "saved", invoice: saved, sentPatch });
      setSavedAt(new Date());
      return true;
    } catch (error) {
      toastApiError(error, "Could not save the invoice");
      return false;
    }
  }, [form, isReadOnly, update]);

  useAutosave({ isDirty: dirty, isInFlight: update.isPending, save: () => void save() });

  const actions = useReviewActions({ invoiceId: queue.currentId, canConfirm, ensureSaved: save, dispatchQueue: queue.dispatch });

  const navigate = useCallback(
    (direction: "next" | "previous") => {
      void save();
      queue.dispatch({ type: direction });
    },
    [save, queue],
  );

  const runShortcut = useCallback(
    (action: ShortcutAction) => {
      switch (action) {
        case "confirm":
          void actions.confirm();
          return;
        case "reject":
          setOverlay("reject");
          return;
        case "duplicate":
          setOverlay("duplicate");
          return;
        case "help":
          setOverlay((current) => (current === "help" ? null : "help"));
          return;
        case "undo":
          dispatchForm({ type: "undo" });
          return;
        case "next":
        case "previous":
          navigate(action);
          return;
        case "escape":
          (document.activeElement as HTMLElement | null)?.blur();
          return;
      }
    },
    [actions, navigate],
  );

  const isModal = overlay !== null || actions.gate !== null;
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const action = resolveShortcut(event);
      if (!action) return;
      if (isModal) {
        if (action === "escape") setOverlay(null);
        return; // dialogs own their keys
      }
      if (queue.currentId === null) return;
      event.preventDefault();
      runShortcut(action);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isModal, queue.currentId, runShortcut]);

  const computed = useMemo(() => computeInvoice(form.draft.lines, form.draft.header.supply_type), [form.draft.lines, form.draft.header.supply_type]);
  const issues = invoice?.issues ?? [];
  const onResolve = (issueId: string, note: string) => {
    if (!invoice) return;
    resolveIssue.mutate({ invoiceId: invoice.id, issueId, note }, { onError: (error) => toastApiError(error, "Could not resolve the issue") });
  };

  const saveStatus: SaveStatus = update.isPending ? { kind: "saving" } : dirty ? { kind: "dirty" } : savedAt ? { kind: "saved", at: savedAt } : { kind: "clean" };
  const summary = queue.currentId ? queue.summaryOf(queue.currentId) : undefined;
  const headline = invoice ?? summary ?? null;

  if (queue.error) {
    return (
      <EmptyState
        icon={Inbox}
        title="Could not load the review queue"
        description={queue.error.message}
        action={
          <Button variant="outline" size="sm" onClick={queue.refetch}>
            <RefreshCw /> Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col gap-3">
      <QueueHeader
        position={queue.position}
        total={queue.total}
        remaining={queue.remaining}
        invoice={headline}
        saveStatus={saveStatus}
        canConfirm={canConfirm}
        isBusy={actions.isBusy}
        onConfirm={() => void actions.confirm()}
        onReject={() => setOverlay("reject")}
        onDuplicate={() => setOverlay("duplicate")}
        onPrevious={() => navigate("previous")}
        onNext={() => navigate("next")}
        onHelp={() => setOverlay("help")}
      />
      {queue.isPending ? (
        <Skeleton className="flex-1" />
      ) : queue.currentId === null ? (
        <EmptyState icon={Inbox} title="Queue clear" description="Every extracted invoice has been reviewed. New uploads land here once extraction finishes." className="flex-1 justify-center" />
      ) : (
        <SplitPane
          left={<PdfPane documentId={invoice ? documentIdOf(invoice) : null} />}
          right={
            <div ref={formRef} className="space-y-4 p-4">
              {invoice && isFormForInvoice ? (
                <>
                  <PartyCard
                    partyId={invoice.party}
                    partyName={invoice.party_name}
                    direction={invoice.direction}
                    issues={issuesAt(issues, (location) => location.kind === "party")}
                    onResolve={onResolve}
                    isReadOnly={isReadOnly}
                  />
                  <InvoiceForm
                    header={form.draft.header}
                    isLowConfidence={isLowConfidence(invoice.confidence)}
                    issues={issues}
                    onChange={(field, value) => dispatchForm({ type: "header", field, value })}
                    onResolve={onResolve}
                    isReadOnly={isReadOnly}
                  />
                  <LineTable
                    lines={form.draft.lines}
                    computed={computed.lines}
                    supplyType={form.draft.header.supply_type}
                    issues={issues}
                    onChange={(index, column, value) => dispatchForm({ type: "line", index, column, value })}
                    onAdd={() => dispatchForm({ type: "addLine" })}
                    onRemove={(index) => dispatchForm({ type: "removeLine", index })}
                    onResolve={onResolve}
                    isReadOnly={isReadOnly}
                  />
                  <TotalsPanel
                    client={computed.totals}
                    server={totalsFromInvoice(invoice)}
                    isDirty={dirty}
                    issues={issuesAt(issues, (location) => location.kind === "totals" || location.kind === "general")}
                    onResolve={onResolve}
                    isReadOnly={isReadOnly}
                  />
                </>
              ) : detail.isError ? (
                <EmptyState icon={Inbox} title="Could not load this invoice" description={detail.error.message} />
              ) : (
                <div className="space-y-3" aria-busy>
                  <Skeleton className="h-20" />
                  <Skeleton className="h-40" />
                  <Skeleton className="h-32" />
                </div>
              )}
            </div>
          }
        />
      )}
      <RejectDialog open={overlay === "reject"} onOpenChange={(open) => setOverlay(open ? "reject" : null)} isPending={actions.isBusy} onSubmit={(reason) => { setOverlay(null); void actions.reject(reason); }} />
      <DuplicateDialog open={overlay === "duplicate"} onOpenChange={(open) => setOverlay(open ? "duplicate" : null)} isPending={actions.isBusy} onSubmit={(duplicateOf) => { setOverlay(null); void actions.markDuplicate(duplicateOf); }} />
      <ConfirmGateDialog open={actions.gate !== null} issues={actions.gate?.issues ?? []} onOpenChange={(open) => { if (!open) actions.closeGate(); }} onForce={() => void actions.confirm(true)} isPending={actions.isBusy} />
      <ShortcutOverlay open={overlay === "help"} onOpenChange={(open) => setOverlay(open ? "help" : null)} />
    </div>
  );
}
