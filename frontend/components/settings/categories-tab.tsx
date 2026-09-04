"use client";

import { Plus, Tags } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "@/components/primitives/checkbox";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { EmptyState } from "@/components/primitives/empty-state";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { useCategories, useDeleteCategory, useSaveCategory, type CategoryInput } from "@/lib/categories";
import { ICON_STROKE } from "@/lib/constants";
import { toastApiError } from "@/lib/toast";
import type { Category } from "@/lib/types";

function fromCategory(category: Category | null): CategoryInput {
  return {
    name: category?.name ?? "",
    parent: category?.parent ?? null,
    itc_eligible: category?.itc_eligible ?? true,
    section_17_5_ref: category?.section_17_5_ref ?? "",
    tally_ledger_name: category?.tally_ledger_name ?? "",
    is_recurring_hint: category?.is_recurring_hint ?? false,
  };
}

function CategoryDialog({ category, parents, open, onOpenChange }: { category: Category | null; parents: Category[]; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [form, setForm] = useState<CategoryInput>(() => fromCategory(category));
  const save = useSaveCategory();
  const set = <K extends keyof CategoryInput>(key: K, value: CategoryInput[K]) => setForm((current) => ({ ...current, [key]: value }));

  const submit = () =>
    save.mutate(
      { id: category?.id, body: form },
      {
        onSuccess: () => {
          toast({ title: category ? "Category updated" : "Category created" });
          onOpenChange(false);
        },
        onError: (error) => toastApiError(error, "Could not save category"),
      },
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{category ? "Edit category" : "New category"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="cat-name" label="Name" required className="sm:col-span-2">
            <Input id="cat-name" value={form.name} onChange={(event) => set("name", event.target.value)} />
          </Field>
          <Field id="cat-parent" label="Parent">
            <NativeSelect id="cat-parent" value={form.parent ?? ""} onChange={(event) => set("parent", event.target.value || null)}>
              <option value="">None</option>
              {parents
                .filter((parent) => parent.id !== category?.id)
                .map((parent) => (
                  <option key={parent.id} value={parent.id}>
                    {parent.name}
                  </option>
                ))}
            </NativeSelect>
          </Field>
          <Field id="cat-tally" label="Tally ledger name">
            <Input id="cat-tally" value={form.tally_ledger_name ?? ""} onChange={(event) => set("tally_ledger_name", event.target.value)} />
          </Field>
          <Field id="cat-175" label="Section 17(5) reference" hint="Set when ITC is blocked under this clause.">
            <Input id="cat-175" value={form.section_17_5_ref ?? ""} onChange={(event) => set("section_17_5_ref", event.target.value)} />
          </Field>
          <div className="flex flex-col gap-2 text-sm">
            <label className="flex items-center gap-2">
              <Checkbox checked={form.itc_eligible ?? true} onChange={(event) => set("itc_eligible", event.target.checked)} /> ITC eligible
            </label>
            <label className="flex items-center gap-2">
              <Checkbox checked={form.is_recurring_hint ?? false} onChange={(event) => set("is_recurring_hint", event.target.checked)} /> Recurring hint (forecast)
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={form.name.trim() === "" || save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CategoriesTab({ canEdit }: { canEdit: boolean }) {
  const categories = useCategories();
  const remove = useDeleteCategory();
  const [editing, setEditing] = useState<{ category: Category | null } | null>(null);
  const [deleting, setDeleting] = useState<Category | null>(null);
  const byId = new Map((categories.data ?? []).map((category) => [category.id, category]));

  const confirmDelete = () => {
    if (!deleting) return;
    remove.mutate(deleting.id, {
      onSuccess: () => {
        toast({ title: "Category deleted" });
        setDeleting(null);
      },
      onError: (error) => toastApiError(error, "Could not delete category"),
    });
  };

  return (
    <div className="space-y-4">
      {canEdit && (
        <Button onClick={() => setEditing({ category: null })}>
          <Plus size={16} strokeWidth={ICON_STROKE} aria-hidden /> New category
        </Button>
      )}
      <QueryState isPending={categories.isPending} error={categories.error} onRetry={() => void categories.refetch()}>
        {categories.data?.length === 0 ? (
          <EmptyState icon={Tags} title="No categories" description="System categories are seeded per org; add your own for Tally ledgers." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Parent</TableHead>
                <TableHead>ITC</TableHead>
                <TableHead>17(5)</TableHead>
                <TableHead>Tally ledger</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {categories.data?.map((category) => (
                <TableRow key={category.id}>
                  <TableCell>
                    {category.name} {category.is_system && <StatusBadge status="system" tone="muted" label="system" />}
                  </TableCell>
                  <TableCell className="text-muted">{category.parent ? (byId.get(category.parent)?.name ?? "—") : "—"}</TableCell>
                  <TableCell>{category.itc_eligible ? "eligible" : "blocked"}</TableCell>
                  <TableCell className="text-muted">{category.section_17_5_ref || "—"}</TableCell>
                  <TableCell className="text-muted">{category.tally_ledger_name || "—"}</TableCell>
                  <TableCell className="text-right">
                    {canEdit && !category.is_system && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => setEditing({ category })}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" className="text-danger" onClick={() => setDeleting(category)}>
                          Delete
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      {editing && (
        <CategoryDialog key={editing.category?.id ?? "new"} category={editing.category} parents={categories.data ?? []} open onOpenChange={(open) => !open && setEditing(null)} />
      )}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.name ?? ""}"?`}
        description="Invoice lines keep their category reference on the server; only the category label is removed."
        confirmLabel="Delete"
        destructive
        isPending={remove.isPending}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
