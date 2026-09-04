"use client";

import { Bookmark, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Field } from "@/components/primitives/field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ICON_STROKE } from "@/lib/constants";
import type { InvoiceFilters } from "@/lib/invoice-filters";
import { deleteView, loadSavedViews, saveView, type SavedView } from "@/lib/saved-views";

export interface SavedViewsMenuProps {
  userId: string;
  filters: InvoiceFilters;
  onApply: (filters: InvoiceFilters) => void;
}

/** Per-user saved filter sets in localStorage (no server endpoint in §10). */
export function SavedViewsMenu({ userId, filters, onApply }: SavedViewsMenuProps) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [name, setName] = useState("");

  useEffect(() => setViews(loadSavedViews(userId)), [userId]);

  const save = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setViews(saveView(userId, { name: trimmed, params: filters }));
    setName("");
    setIsSaving(false);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <Bookmark strokeWidth={ICON_STROKE} aria-hidden /> Views{views.length > 0 && ` (${views.length})`}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          <DropdownMenuLabel className="text-xs text-muted">Saved views</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {views.length === 0 && <p className="px-2 py-1.5 text-xs text-muted">None yet — save the current filters.</p>}
          {views.map((view) => (
            <DropdownMenuItem key={view.name} className="flex items-center justify-between gap-2" onSelect={() => onApply(view.params)}>
              <span className="truncate">{view.name}</span>
              <button
                type="button"
                aria-label={`Delete view ${view.name}`}
                className="text-muted hover:text-danger"
                onClick={(event) => {
                  event.stopPropagation();
                  setViews(deleteView(userId, view.name));
                }}
              >
                <Trash2 size={14} strokeWidth={ICON_STROKE} aria-hidden />
              </button>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setIsSaving(true)}>Save current filters…</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={isSaving} onOpenChange={setIsSaving}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save view</DialogTitle>
          </DialogHeader>
          <Field id="view-name" label="Name" required>
            <Input id="view-name" value={name} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => event.key === "Enter" && save()} autoFocus />
          </Field>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsSaving(false)}>
              Cancel
            </Button>
            <Button onClick={save} disabled={name.trim() === ""}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
