"use client";

import { useCallback, useState } from "react";
import { toast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api";
import { issuesFromProblem, useConfirmInvoice, useMarkDuplicate, useRejectInvoice, type ValidationIssue } from "@/lib/invoices";
import { toastApiError } from "@/lib/toast";
import type { QueueAction } from "./queue-state";

const HTTP_BAD_REQUEST = 400;

export interface ReviewActionsArgs {
  invoiceId: string | null;
  canConfirm: boolean;
  /** Flushes unsaved edits; resolves false when the save failed (the decision is then aborted). */
  ensureSaved: () => Promise<boolean>;
  dispatchQueue: (action: QueueAction) => void;
}

export interface ConfirmGate {
  invoiceId: string;
  issues: ValidationIssue[];
}

export interface ReviewActionsApi {
  confirm: (force?: boolean) => Promise<void>;
  reject: (reason: string) => Promise<void>;
  markDuplicate: (duplicateOf?: string) => Promise<void>;
  gate: ConfirmGate | null;
  closeGate: () => void;
  isBusy: boolean;
}

/**
 * Confirm / reject / duplicate with optimistic advance: the queue moves on immediately and
 * rolls back if the server refuses. A 400 carrying errors.issues opens the confirm gate.
 */
export function useReviewActions({ invoiceId, canConfirm, ensureSaved, dispatchQueue }: ReviewActionsArgs): ReviewActionsApi {
  const confirmMutation = useConfirmInvoice();
  const rejectMutation = useRejectInvoice();
  const duplicateMutation = useMarkDuplicate();
  const [gate, setGate] = useState<ConfirmGate | null>(null);

  const decide = useCallback(
    async (label: string, run: (id: string) => Promise<unknown>, onError?: (error: unknown, id: string) => boolean) => {
      if (!invoiceId) return;
      const id = invoiceId;
      if (!(await ensureSaved())) return;
      dispatchQueue({ type: "markDone", id });
      try {
        await run(id);
        toast({ title: label });
      } catch (error) {
        dispatchQueue({ type: "unmarkDone", id });
        if (onError?.(error, id)) return;
        toastApiError(error, `Could not ${label.toLowerCase()}`);
      }
    },
    [invoiceId, ensureSaved, dispatchQueue],
  );

  const confirm = useCallback(
    async (force = false) => {
      if (!canConfirm) {
        toast({ title: "Viewers cannot confirm invoices" });
        return;
      }
      setGate(null);
      await decide("Confirmed", (id) => confirmMutation.mutateAsync({ id, force }), (error, id) => {
        const issues = error instanceof ApiError && error.status === HTTP_BAD_REQUEST ? issuesFromProblem(error.problem.errors) : [];
        if (issues.length === 0) return false;
        setGate({ invoiceId: id, issues });
        return true;
      });
    },
    [canConfirm, decide, confirmMutation],
  );

  const reject = useCallback((reason: string) => decide("Rejected", (id) => rejectMutation.mutateAsync({ id, reason })), [decide, rejectMutation]);
  const markDuplicate = useCallback(
    (duplicateOf?: string) => decide("Marked duplicate", (id) => duplicateMutation.mutateAsync({ id, duplicateOf })),
    [decide, duplicateMutation],
  );

  return {
    confirm,
    reject,
    markDuplicate,
    gate,
    closeGate: () => setGate(null),
    isBusy: confirmMutation.isPending || rejectMutation.isPending || duplicateMutation.isPending,
  };
}
