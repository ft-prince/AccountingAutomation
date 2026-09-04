"use client";

import Link from "next/link";
import { MoneyText } from "@/components/primitives/money-text";
import { QueryState } from "@/components/primitives/query-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Driver } from "@/lib/forecast";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const RECURRING_ANCHOR = "#recurring";
const FIXED_LINES_HREF = "/settings?tab=forecast";

function sourceLink(driver: Driver): { href: string; label: string } | null {
  if (driver.source === "invoice") return driver.party ? { href: `/invoices?party=${driver.party}`, label: "invoices" } : { href: "/invoices", label: "invoices" };
  if (driver.source === "recurring") return { href: RECURRING_ANCHOR, label: "recurring" };
  if (driver.source === "fixed_line") return { href: FIXED_LINES_HREF, label: "fixed line" };
  return null;
}

/** §11 drivers table: the scheduled inflows/outflows behind the deterministic line, with source links. */
export function DriversTable({ drivers, isPending, error, onRetry }: { drivers: readonly Driver[] | undefined; isPending: boolean; error: unknown; onRetry: () => void }) {
  return (
    <section aria-label="Drivers" className="rounded-card border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold">Drivers</h2>
      <p className="text-xs text-muted">What is scheduled inside the horizon, largest first as the API orders them.</p>
      <QueryState isPending={isPending} error={error} onRetry={onRetry} skeletonClassName="mt-3 h-40 w-full">
        {drivers && drivers.length === 0 ? (
          <p className="mt-3 text-sm text-muted">Nothing scheduled inside the horizon.</p>
        ) : (
          <Table className="mt-3">
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Driver</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {drivers?.map((driver, index) => {
                const link = sourceLink(driver);
                return (
                  <TableRow key={`${driver.date}-${driver.label}-${index}`}>
                    <TableCell className="tabular-nums">{formatDate(driver.date)}</TableCell>
                    <TableCell className="font-medium">{driver.label}</TableCell>
                    <TableCell>
                      {link ? <Link href={link.href} className="underline underline-offset-2 hover:text-accent">{link.label}</Link> : <span className="text-muted">{driver.source}</span>}
                    </TableCell>
                    <TableCell className="text-right">
                      <MoneyText value={driver.amount} className={cn("font-medium", driver.direction === "inflow" ? "text-success" : "text-danger")} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </QueryState>
    </section>
  );
}
