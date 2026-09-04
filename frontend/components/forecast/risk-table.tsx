"use client";

import Link from "next/link";
import { QueryState } from "@/components/primitives/query-state";
import { RiskBandBadge } from "@/components/primitives/risk-band-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { CustomerRisk } from "@/lib/forecast";

/** §8.5 payment-delay risk per customer with the drivers listed. */
export function RiskTable({ rows, isPending, error, onRetry }: { rows: readonly CustomerRisk[] | undefined; isPending: boolean; error: unknown; onRetry: () => void }) {
  return (
    <section aria-label="Customer risk" className="rounded-card border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold">Customer payment risk</h2>
      <p className="text-xs text-muted">Logistic-style score from days-to-pay, trend, share overdue and credit utilisation.</p>
      <QueryState isPending={isPending} error={error} onRetry={onRetry} skeletonClassName="mt-3 h-40 w-full">
        {rows && rows.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No customers with enough paid invoices to score.</p>
        ) : (
          <Table className="mt-3">
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Band</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead className="text-right">Mean days</TableHead>
                <TableHead>Drivers</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows?.map((row) => (
                <TableRow key={row.party}>
                  <TableCell className="font-medium">
                    <Link href={`/parties/${row.party}`} className="hover:text-accent">{row.party_name || row.party}</Link>
                  </TableCell>
                  <TableCell><RiskBandBadge band={row.band} /></TableCell>
                  <TableCell className="text-right tabular-nums">{row.score}</TableCell>
                  <TableCell className="text-right tabular-nums">{row.mean_days}</TableCell>
                  <TableCell className="text-xs text-muted">{row.drivers.length > 0 ? row.drivers.join(" · ") : "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
    </section>
  );
}
