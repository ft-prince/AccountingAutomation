"use client";

import { FileUp } from "lucide-react";
import { useState } from "react";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { BANK_MAPPINGS, useImportStatement, type BankMapping, type ImportResult } from "@/lib/bank";
import { isMappingUsable, previewStatement, type ImportPreview } from "@/lib/bank-import";
import { ICON_STROKE } from "@/lib/constants";
import { toastApiError } from "@/lib/toast";
import type { BankAccount } from "@/lib/types";

const PREVIEW_BYTES = 64 * 1024;
const MAPPING_LABEL: Record<BankMapping, string> = { auto: "Detect automatically", hdfc: "HDFC", icici: "ICICI", sbi: "SBI", generic: "Generic (date, description, amount)" };

export interface ImportWizardProps {
  accounts: readonly BankAccount[];
  defaultAccountId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (result: ImportResult) => void;
}

/** Step 1 choose file + account → step 2 preview the first rows with guessed columns → import. */
export function ImportWizard({ accounts, defaultAccountId, open, onOpenChange, onImported }: ImportWizardProps) {
  const [file, setFile] = useState<File | null>(null);
  const [accountId, setAccountId] = useState(defaultAccountId);
  const [mapping, setMapping] = useState<BankMapping>("auto");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const importStatement = useImportStatement();

  const choose = async (chosen: File | null) => {
    setFile(chosen);
    setPreview(null);
    if (!chosen) return;
    if (/\.csv$/i.test(chosen.name) || chosen.type.includes("csv") || chosen.type.startsWith("text/")) {
      const text = await chosen.slice(0, PREVIEW_BYTES).text();
      setPreview(previewStatement(text));
    }
  };

  const submit = () => {
    if (!file || !accountId) return;
    importStatement.mutate(
      { file, account: accountId, mapping },
      {
        onSuccess: (result) => {
          toast({ title: `${result.rows_imported} rows imported`, description: `${result.rows_duplicate} duplicates skipped of ${result.rows_total} · mapping ${result.mapping}` });
          onImported(result);
          onOpenChange(false);
        },
        onError: (error) => toastApiError(error, "Import failed"),
      },
    );
  };

  const isCsvPreviewBad = preview !== null && !isMappingUsable(preview.columns) && mapping === "auto";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import bank statement</DialogTitle>
          <DialogDescription>CSV or XLSX from your bank. Rows already imported are skipped by their hash.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="import-file" label="Statement file" required className="sm:col-span-3">
            <input id="import-file" type="file" accept=".csv,.xlsx,.xls,text/csv" className="block w-full text-sm file:mr-3 file:rounded-full file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm" onChange={(event) => choose(event.target.files?.[0] ?? null)} />
          </Field>
          <Field id="import-account" label="Account" required>
            <NativeSelect id="import-account" value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">Choose…</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="import-mapping" label="Column mapping" hint="Override if auto-detect guesses wrong.">
            <NativeSelect id="import-mapping" value={mapping} onChange={(event) => setMapping(event.target.value as BankMapping)}>
              {BANK_MAPPINGS.map((value) => (
                <option key={value} value={value}>
                  {MAPPING_LABEL[value]}
                </option>
              ))}
            </NativeSelect>
          </Field>
        </div>

        {preview && preview.headers.length > 0 && (
          <section aria-label="Preview" className="space-y-2">
            <p className="text-xs text-muted">First {preview.rows.length} rows · guessed roles shown under each header. The server does the authoritative parse.</p>
            <div className="max-h-64 overflow-auto rounded-card border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    {preview.columns.map((column) => (
                      <TableHead key={column.index} className="whitespace-nowrap">
                        {column.header}
                        <span className={column.role === "ignore" ? "block text-xs font-normal text-muted" : "block text-xs font-normal text-accent"}>{column.role}</span>
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.rows.map((row, rowIndex) => (
                    <TableRow key={rowIndex}>
                      {preview.headers.map((_, cellIndex) => (
                        <TableCell key={cellIndex} className="max-w-[14rem] truncate text-xs tabular-nums">
                          {row[cellIndex] ?? ""}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {isCsvPreviewBad && (
              <p role="alert" className="text-xs text-warning">
                Could not spot a date and an amount (or debit/credit pair) in the headers. Pick a bank mapping above or the import may fail.
              </p>
            )}
          </section>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={importStatement.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!file || !accountId || importStatement.isPending}>
            <FileUp strokeWidth={ICON_STROKE} aria-hidden /> {importStatement.isPending ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
