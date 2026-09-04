"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Field } from "@/components/primitives/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useImport2b, useRunReconciliation } from "@/lib/reconciliation";
import { toastApiError } from "@/lib/toast";
import { cn } from "@/lib/utils";

const PERIOD_PATTERN = /^(0[1-9]|1[0-2])\d{4}$/; // MMYYYY as the API expects
const ACCEPTED = ".json,.xlsx";

function defaultPeriod(today = new Date()): string {
  // GSTR-2B for the previous month is what an org reconciles this month.
  const previous = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  return `${String(previous.getMonth() + 1).padStart(2, "0")}${previous.getFullYear()}`;
}

/** Import a GSTR-2B JSON/XLSX for a period, then run matching; owner/accountant only. */
export function ImportPanel({ canImport, onImported }: { canImport: boolean; onImported: (batchId: string) => void }) {
  const importBatch = useImport2b();
  const run = useRunReconciliation();
  const [period, setPeriod] = useState(defaultPeriod);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const periodError = period && !PERIOD_PATTERN.test(period) ? "MMYYYY, e.g. 082026" : undefined;
  const isBusy = importBatch.isPending || run.isPending;

  const submit = () => {
    if (!file || periodError) return;
    importBatch.mutate(
      { file, period },
      {
        onSuccess: (batch) => {
          toast({ title: "2B imported", description: `${batch.filename} · period ${batch.period}` });
          run.mutate(batch.id, {
            onSuccess: () => { toast({ title: "Reconciliation run" }); onImported(batch.id); setFile(null); },
            onError: (error) => { toastApiError(error, "Matching failed"); onImported(batch.id); },
          });
        },
        onError: (error) => toastApiError(error, "Import failed"),
      },
    );
  };

  if (!canImport) return <p className="text-sm text-muted">Only owners and accountants can import GSTR-2B files.</p>;

  return (
    <section aria-label="Import GSTR-2B" className="grid gap-4 rounded-card border border-border bg-surface p-5 md:grid-cols-[auto_1fr_auto] md:items-end">
      <Field id="recon-period" label="Period (MMYYYY)" error={periodError}>
        <Input id="recon-period" value={period} maxLength={6} inputMode="numeric" className="w-32" onChange={(event) => setPeriod(event.target.value.replace(/\D/g, ""))} />
      </Field>
      <div
        role="button"
        tabIndex={0}
        aria-label="Drop the GSTR-2B file here"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
        onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => { event.preventDefault(); setIsDragging(false); const dropped = event.dataTransfer.files[0]; if (dropped) setFile(dropped); }}
        className={cn("flex min-h-[3.5rem] cursor-pointer items-center justify-center gap-2 rounded-card border border-dashed px-4 text-sm transition-colors", isDragging ? "border-accent text-accent" : "border-border text-muted hover:border-muted")}
      >
        <Upload size={16} strokeWidth={ICON_STROKE} aria-hidden />
        {file ? <span className="text-foreground">{file.name}</span> : "Drop the GSTR-2B JSON or XLSX, or click to choose"}
        <input ref={inputRef} type="file" accept={ACCEPTED} className="sr-only" aria-label="GSTR-2B file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </div>
      <Button onClick={submit} disabled={!file || Boolean(periodError) || isBusy}>
        {importBatch.isPending ? "Importing…" : run.isPending ? "Matching…" : "Import & run"}
      </Button>
    </section>
  );
}
