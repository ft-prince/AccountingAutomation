"use client";

import { Download, FileUp } from "lucide-react";
import { useState } from "react";
import { Field } from "@/components/primitives/field";
import { MoneyText } from "@/components/primitives/money-text";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { INVOICE_IMPORT_TEMPLATE_URL, useImportInvoices, type InvoiceImportResult } from "@/lib/invoice-queries";
import { toastApiError } from "@/lib/toast";

/** The importer answers 207: some rows become invoices, some fail. Both halves are shown. */
export function ImportResultPanel({ result }: { result: InvoiceImportResult }) {
  const isPartial = result.invoices > 0 && result.failed > 0;
  return (
    <section aria-label="Import result" className="space-y-3">
      <p className={isPartial ? "text-sm text-warning" : "text-sm"} role="status">
        {result.invoices} invoice{result.invoices === 1 ? "" : "s"} created · {result.failed} row{result.failed === 1 ? "" : "s"} failed
        {isPartial && " — partial import: the created invoices are saved, the failed rows are not."}
      </p>

      {result.created.length > 0 && (
        <div className="rounded-card border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Created invoice</TableHead>
                <TableHead className="text-right">Total (server)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.created.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell>{invoice.invoice_number}</TableCell>
                  <TableCell className="text-right">
                    <MoneyText value={invoice.total} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {result.errors.length > 0 && (
        <div className="rounded-card border border-danger">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">Row</TableHead>
                <TableHead className="w-40">Invoice</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.errors.map((error) => (
                <TableRow key={`${error.row}-${error.invoice_number}`}>
                  <TableCell className="tabular-nums">{error.row}</TableCell>
                  <TableCell>{error.invoice_number || "—"}</TableCell>
                  <TableCell className="text-danger">{error.error}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}

export interface InvoiceImportWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Step 1 download the template and choose a CSV → step 2 the per-row result of the 207. */
export function InvoiceImportWizard({ open, onOpenChange }: InvoiceImportWizardProps) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<InvoiceImportResult | null>(null);
  const importInvoices = useImportInvoices();

  const reset = () => {
    setFile(null);
    setResult(null);
  };

  const close = () => {
    onOpenChange(false);
    reset();
  };

  const submit = () => {
    if (!file) return;
    importInvoices.mutate(file, {
      onSuccess: (imported) => {
        setResult(imported);
        toast({ title: `${imported.invoices} created, ${imported.failed} failed`, description: "Created invoices are in the review queue." });
      },
      onError: (error) => toastApiError(error, "Import failed"),
    });
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import invoices from CSV</DialogTitle>
          <DialogDescription>One row per line item; rows sharing an invoice number become one invoice. The server recomputes all tax.</DialogDescription>
        </DialogHeader>

        <a href={INVOICE_IMPORT_TEMPLATE_URL} download className="inline-flex w-fit items-center gap-2 text-sm text-accent underline underline-offset-2">
          <Download size={16} strokeWidth={ICON_STROKE} aria-hidden /> Download the CSV template
        </a>

        <Field id="invoice-import-file" label="CSV file" required>
          <input
            id="invoice-import-file"
            type="file"
            accept=".csv,text/csv"
            className="block w-full text-sm file:mr-3 file:rounded-full file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setResult(null);
            }}
          />
        </Field>

        {result && <ImportResultPanel result={result} />}

        <DialogFooter>
          <Button variant="outline" onClick={close} disabled={importInvoices.isPending}>
            {result ? "Done" : "Cancel"}
          </Button>
          <Button onClick={submit} disabled={!file || importInvoices.isPending}>
            <FileUp strokeWidth={ICON_STROKE} aria-hidden /> {importInvoices.isPending ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
