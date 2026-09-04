"use client";

import { CheckCheck, Copy, Download, ExternalLink } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { downloadCsv, toCsv } from "@/lib/csv";
import { invoicesExportUrl, type InvoiceFilters } from "@/lib/invoice-filters";
import { useBulkConfirm, useMarkDuplicate } from "@/lib/invoice-queries";
import { toast } from "@/hooks/use-toast";
import { toastApiError } from "@/lib/toast";
import type { InvoiceList } from "@/lib/types";

const CSV_HEADERS = ["invoice_number", "invoice_date", "due_date", "direction", "party_name", "taxable_value", "cgst", "sgst", "igst", "cess", "total", "amount_paid", "outstanding", "payment_status", "status", "validation_status", "confidence", "fy", "period_month", "issue_count"] as const;

export interface BulkActionBarProps {
  selectedIds: string[];
  rows: InvoiceList[];
  filters: InvoiceFilters;
  canConfirm: boolean;
  onDone: () => void;
}

export function BulkActionBar({ selectedIds, rows, filters, canConfirm, onDone }: BulkActionBarProps) {
  const [pending, setPending] = useState<"confirm" | "duplicate" | null>(null);
  const bulkConfirm = useBulkConfirm();
  const markDuplicate = useMarkDuplicate();
  const count = selectedIds.length;

  const exportView = () => {
    const csv = toCsv(CSV_HEADERS, rows.map((row) => CSV_HEADERS.map((key) => row[key] ?? "")));
    downloadCsv(`invoices-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  };

  const runConfirm = () =>
    bulkConfirm.mutate(
      { ids: selectedIds },
      {
        onSuccess: (result) => {
          const outcomes = Object.values(result.results);
          const confirmed = outcomes.filter((outcome) => outcome === "confirmed").length;
          toast({ title: `${confirmed} of ${count} confirmed`, description: confirmed < count ? "The rest still have unresolved issues; open them in review." : undefined });
          setPending(null);
          onDone();
        },
        onError: (error) => toastApiError(error, "Bulk confirm failed"),
      },
    );

  const runDuplicate = () =>
    markDuplicate.mutate(selectedIds, {
      onSuccess: (result) => {
        toast({ title: `${result.total - result.failed} marked duplicate`, description: result.failed > 0 ? `${result.failed} failed` : undefined, variant: result.failed > 0 ? "destructive" : "default" });
        setPending(null);
        onDone();
      },
    });

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-sm">
      <span className="px-1 tabular-nums text-muted">{count} selected</span>
      <Button size="sm" disabled={count === 0 || !canConfirm} title={canConfirm ? undefined : "Your role cannot confirm invoices"} onClick={() => setPending("confirm")}>
        <CheckCheck strokeWidth={ICON_STROKE} aria-hidden /> Confirm
      </Button>
      <Button size="sm" variant="outline" disabled={count === 0 || !canConfirm} onClick={() => setPending("duplicate")}>
        <Copy strokeWidth={ICON_STROKE} aria-hidden /> Mark duplicate
      </Button>
      <span className="mx-1 h-5 w-px bg-border" aria-hidden />
      <Button size="sm" variant="outline" disabled={rows.length === 0} onClick={exportView}>
        <Download strokeWidth={ICON_STROKE} aria-hidden /> CSV of this page
      </Button>
      <Button size="sm" variant="ghost" asChild>
        <a href={invoicesExportUrl(filters)} target="_blank" rel="noreferrer">
          <ExternalLink strokeWidth={ICON_STROKE} aria-hidden /> Full export (server)
        </a>
      </Button>

      <ConfirmDialog
        open={pending === "confirm"}
        onOpenChange={(open) => !open && setPending(null)}
        title={`Confirm ${count} invoice${count === 1 ? "" : "s"}?`}
        description="Only invoices whose rules score passes every check will confirm; the rest stay in review. Confirmed invoices count in every report."
        confirmLabel="Confirm invoices"
        isPending={bulkConfirm.isPending}
        onConfirm={runConfirm}
      />
      <ConfirmDialog
        open={pending === "duplicate"}
        onOpenChange={(open) => !open && setPending(null)}
        title={`Mark ${count} as duplicate?`}
        description="Duplicates are excluded from reports and GST returns. This can be undone from the review screen."
        confirmLabel="Mark duplicate"
        destructive
        isPending={markDuplicate.isPending}
        onConfirm={runDuplicate}
      />
    </div>
  );
}
