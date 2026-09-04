"use client";

import Big from "big.js";
import { useEffect, useState } from "react";
import { MoneyText } from "@/components/primitives/money-text";
import { QueryState } from "@/components/primitives/query-state";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { allocationRemainder, allocationsToSubmit, hasNegativeAllocation, isOverAllocated, suggestedAllocation, type AllocationDraft } from "@/lib/allocation";
import { formatDate } from "@/lib/format";
import { orZero } from "@/lib/money";
import { useAllocatePayment, useOpenInvoices } from "@/lib/payments";
import { toastApiError } from "@/lib/toast";
import type { Payment } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface AllocateDialogProps {
  payment: Payment | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Allocates the unallocated part of a payment across the party's open invoices. The running
 * remainder is recomputed in big.js on every keystroke and the submit is blocked the instant it
 * would go negative; the server's Decimal result is authoritative.
 */
export function AllocateDialog({ payment, onOpenChange }: AllocateDialogProps) {
  const partyId = payment?.party ?? "";
  const invoices = useOpenInvoices(partyId, payment?.direction ?? "");
  const allocate = useAllocatePayment();
  const [drafts, setDrafts] = useState<AllocationDraft[]>([]);

  useEffect(() => {
    setDrafts((invoices.data ?? []).map((invoice) => ({ invoice: invoice.id, amount: "" })));
  }, [invoices.data]);

  if (!payment) return null;
  const unallocated = new Big(orZero(payment.amount)).minus(orZero(payment.allocated)).toFixed(2);
  const remainder = allocationRemainder(unallocated, drafts);
  const isNegative = isOverAllocated(unallocated, drafts) || hasNegativeAllocation(drafts);
  const items = allocationsToSubmit(drafts);
  const setAmount = (invoiceId: string, amount: string) => setDrafts((current) => current.map((draft) => (draft.invoice === invoiceId ? { ...draft, amount } : draft)));

  const submit = () =>
    allocate.mutate(
      { paymentId: payment.id, items },
      {
        onSuccess: () => {
          toast({ title: "Allocated", description: `${items.length} invoice${items.length === 1 ? "" : "s"} updated` });
          onOpenChange(false);
        },
        onError: (error) => toastApiError(error, "Allocation rejected"),
      },
    );

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Allocate payment</DialogTitle>
          <DialogDescription>
            {payment.party_name} · {formatDate(payment.date)} · <MoneyText value={orZero(payment.amount)} /> {payment.direction} · already allocated <MoneyText value={orZero(payment.allocated)} />
          </DialogDescription>
        </DialogHeader>

        <div className={cn("flex items-center justify-between rounded-card border px-4 py-3 text-sm", isNegative ? "border-danger text-danger" : "border-border")} role="status" aria-live="polite">
          <span className="text-muted">Remaining to allocate</span>
          <MoneyText value={remainder} className="text-lg font-semibold" />
        </div>
        {isNegative && (
          <p role="alert" className="text-xs text-danger">
            Allocations exceed the payment. Reduce an amount before saving.
          </p>
        )}

        <QueryState isPending={invoices.isPending} error={invoices.error} onRetry={() => invoices.refetch()}>
          {invoices.data && invoices.data.length === 0 ? (
            <p className="text-sm text-muted">No confirmed invoices with an outstanding balance for this party.</p>
          ) : (
            <div className="max-h-[50vh] overflow-auto rounded-card border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead className="text-right">Outstanding</TableHead>
                    <TableHead className="w-44 text-right">Allocate (₹)</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(invoices.data ?? []).map((invoice) => {
                    const draft = drafts.find((entry) => entry.invoice === invoice.id);
                    return (
                      <TableRow key={invoice.id}>
                        <TableCell className="font-medium">{invoice.invoice_number}</TableCell>
                        <TableCell className="tabular-nums">{formatDate(invoice.due_date)}</TableCell>
                        <TableCell className="text-right"><MoneyText value={orZero(invoice.outstanding)} /></TableCell>
                        <TableCell className="text-right">
                          <Input aria-label={`Allocate to ${invoice.invoice_number}`} inputMode="decimal" className="text-right" value={draft?.amount ?? ""} onChange={(event) => setAmount(invoice.id, event.target.value.trim())} />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const withoutThis = drafts.filter((entry) => entry.invoice !== invoice.id);
                              setAmount(invoice.id, suggestedAllocation(orZero(invoice.outstanding), allocationRemainder(unallocated, withoutThis)));
                            }}
                          >
                            Fill
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </QueryState>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={allocate.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={isNegative || items.length === 0 || allocate.isPending}>
            {allocate.isPending ? "Saving…" : `Allocate ${items.length === 0 ? "" : `${items.length} invoice${items.length === 1 ? "" : "s"}`}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
