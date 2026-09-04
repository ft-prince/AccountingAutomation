"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

export interface RejectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (reason: string) => void;
  isPending: boolean;
}

export function RejectDialog({ open, onOpenChange, onSubmit, isPending }: RejectDialogProps) {
  const [reason, setReason] = useState("");
  const canSubmit = reason.trim().length > 0 && !isPending;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit) onSubmit(reason.trim());
          }}
        >
          <DialogHeader>
            <DialogTitle>Reject invoice</DialogTitle>
            <DialogDescription>The reason is recorded on the audit trail and the invoice leaves the queue.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="reject-reason">Reason</Label>
            <textarea
              id="reject-reason"
              autoFocus
              rows={3}
              className="w-full rounded-md border border-input bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Not our invoice / wrong entity / unreadable scan…"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={!canSubmit}>
              {isPending ? "Rejecting…" : "Reject"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
