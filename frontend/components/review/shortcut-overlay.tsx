"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SHORTCUT_BINDINGS } from "@/lib/keyboard";

export interface ShortcutOverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const EXTRA_ROWS: readonly { keys: string; description: string }[] = [
  { keys: "Tab / Shift+Tab", description: "Move between fields" },
  { keys: "Esc", description: "Close dialogs; leave the current field" },
];

export function ShortcutOverlay({ open, onOpenChange }: ShortcutOverlayProps) {
  const rows = [...SHORTCUT_BINDINGS.filter((binding) => binding.action !== "escape"), ...EXTRA_ROWS];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="shortcut-help">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription id="shortcut-help">Letters are ignored while you type in a field.</DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {rows.map((row) => (
            <div key={row.keys} className="contents">
              <dt>
                <kbd className="rounded-md border border-border bg-background px-1.5 py-0.5 font-sans text-xs">{row.keys}</kbd>
              </dt>
              <dd className="text-muted">{row.description}</dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
