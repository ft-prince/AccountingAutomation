"use client";

import Big from "big.js";
import Link from "next/link";
import { MoneyText } from "@/components/primitives/money-text";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, humanize } from "@/lib/format";
import { orZero } from "@/lib/money";
import { isUnallocated } from "@/lib/payments";
import type { Payment } from "@/lib/types";

export function PaymentsTable({ payments, onAllocate }: { payments: readonly Payment[]; onAllocate: (payment: Payment) => void }) {
  if (payments.length === 0) return <p className="py-10 text-center text-sm text-muted">No payments here.</p>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Party</TableHead>
          <TableHead>Direction</TableHead>
          <TableHead>Method · reference</TableHead>
          <TableHead className="text-right">Amount</TableHead>
          <TableHead className="text-right">Allocated</TableHead>
          <TableHead className="text-right">Unallocated</TableHead>
          <TableHead>Invoices</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {payments.map((payment) => {
          const remaining = new Big(orZero(payment.amount)).minus(orZero(payment.allocated)).toFixed(2);
          return (
            <TableRow key={payment.id}>
              <TableCell className="tabular-nums">{formatDate(payment.date)}</TableCell>
              <TableCell>
                {payment.party ? (
                  <Link href={`/parties/${payment.party}`} className="hover:text-accent">
                    {payment.party_name}
                  </Link>
                ) : (
                  <span className="text-muted">Unknown party</span>
                )}
              </TableCell>
              <TableCell>
                <StatusBadge status={payment.direction} tone={payment.direction === "received" ? "success" : "info"} label={payment.direction === "received" ? "Received" : "Made"} />
              </TableCell>
              <TableCell className="text-muted">
                {humanize(payment.method)}
                {payment.reference && <span className="ml-1 font-mono text-xs">{payment.reference}</span>}
              </TableCell>
              <TableCell className="text-right"><MoneyText value={orZero(payment.amount)} className="font-medium" /></TableCell>
              <TableCell className="text-right"><MoneyText value={orZero(payment.allocated)} /></TableCell>
              <TableCell className="text-right"><MoneyText value={remaining} className={isUnallocated(payment) ? "text-warning" : "text-muted"} /></TableCell>
              <TableCell className="max-w-[12rem] truncate text-xs text-muted">{payment.allocations.map((allocation) => allocation.invoice_number).join(", ") || "—"}</TableCell>
              <TableCell className="text-right">
                {isUnallocated(payment) && payment.party && (
                  <Button size="sm" variant="outline" onClick={() => onAllocate(payment)}>
                    Allocate
                  </Button>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
