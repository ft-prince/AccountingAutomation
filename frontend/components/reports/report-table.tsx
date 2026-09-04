import { MoneyText } from "@/components/primitives/money-text";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

import type { ReportTable as ReportTableData } from "./report-rows";

/** One rendered §7.2 table: money columns right-aligned with tabular figures, the rest plain text. */
export function ReportTable({ table }: { table: ReportTableData }) {
  const isMoney = (column: number) => table.moneyColumns.includes(column);
  return (
    <section aria-label={table.title} className="rounded-card border border-border bg-surface">
      <h2 className="border-b border-border px-4 py-3 text-sm font-semibold">{table.title}</h2>
      {table.rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No rows for this period.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              {table.headers.map((header, column) => (
                <TableHead key={header + column} className={cn(isMoney(column) && "text-right")}>
                  {header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {table.rows.map((row, rowIndex) => (
              <TableRow key={rowIndex} className={cn(row[0] === "Total" && "font-semibold")}>
                {row.map((cell, column) => (
                  <TableCell key={column} className={cn(isMoney(column) && "text-right tabular-nums")}>
                    {isMoney(column) && DECIMAL_PATTERN.test(cell) ? <MoneyText value={cell} /> : cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
