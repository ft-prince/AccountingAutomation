"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { ValidationIssue } from "@/lib/invoices";

export interface ConfirmGateDialogProps {
  open: boolean;
  issues: readonly ValidationIssue[];
  onOpenChange: (open: boolean) => void;
  onForce: () => void;
  isPending: boolean;
}

/** The server refused to confirm while error-severity issues remain; the reviewer may override. */
export function ConfirmGateDialog({ open, issues, onOpenChange, onForce, isPending }: ConfirmGateDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Unresolved validation errors</DialogTitle>
          <DialogDescription>Resolve them inline, or confirm anyway — the override is recorded on the audit trail.</DialogDescription>
        </DialogHeader>
        <ul className="space-y-1 text-sm text-danger">
          {issues.map((issue) => (
            <li key={issue.id}>
              <span className="font-medium">{issue.code}</span>
              {issue.field ? ` (${issue.field})` : ""} · {issue.message}
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Back to review
          </Button>
          <Button variant="destructive" onClick={onForce} disabled={isPending}>
            {isPending ? "Confirming…" : "Confirm anyway"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
