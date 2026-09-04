"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface DuplicateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (duplicateOf: string | undefined) => void;
  isPending: boolean;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function DuplicateDialog({ open, onOpenChange, onSubmit, isPending }: DuplicateDialogProps) {
  const [duplicateOf, setDuplicateOf] = useState("");
  const trimmed = duplicateOf.trim();
  const isValid = trimmed === "" || UUID_RE.test(trimmed);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (isValid && !isPending) onSubmit(trimmed || undefined);
          }}
        >
          <DialogHeader>
            <DialogTitle>Mark as duplicate</DialogTitle>
            <DialogDescription>Optionally point at the invoice this one duplicates; leave blank if unknown.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="duplicate-of">Duplicate of (invoice id)</Label>
            <Input id="duplicate-of" autoFocus value={duplicateOf} onChange={(event) => setDuplicateOf(event.target.value)} placeholder="optional UUID" />
            {!isValid && (
              <p role="alert" className="text-xs text-danger">
                That does not look like an invoice id.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!isValid || isPending}>
              {isPending ? "Marking…" : "Mark duplicate"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
