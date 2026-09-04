"use client";

import { createColumnHelper, rowSelectionFeature, tableFeatures, useTable } from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import { Checkbox } from "@/components/primitives/checkbox";
import { MoneyText } from "@/components/primitives/money-text";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ICON_STROKE } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { nextOrdering, SORTABLE_COLUMNS, type InvoiceOrdering } from "@/lib/invoice-filters";
import { orZero } from "@/lib/money";
import type { InvoiceList } from "@/lib/types";
import { cn } from "@/lib/utils";

const features = tableFeatures({ rowSelectionFeature });
const helper = createColumnHelper<typeof features, InvoiceList>();
const EMPTY_ROWS: InvoiceList[] = [];

const columns = helper.columns([
  helper.display({
    id: "select",
    header: ({ table }) => (
      <Checkbox aria-label="Select all on this page" checked={table.getIsAllRowsSelected()} onChange={table.getToggleAllRowsSelectedHandler()} />
    ),
    cell: ({ row }) => <Checkbox aria-label={`Select ${row.original.invoice_number}`} checked={row.getIsSelected()} onChange={row.getToggleSelectedHandler()} onClick={(event) => event.stopPropagation()} />,
  }),
  helper.accessor("invoice_number", { header: "Invoice", cell: ({ getValue }) => <span className="font-medium">{getValue()}</span> }),
  helper.accessor("invoice_date", { id: "invoice_date", header: "Date", cell: ({ getValue }) => <span className="tabular-nums">{formatDate(getValue())}</span> }),
  helper.accessor("party_name", { id: "party_name", header: "Party" }),
  helper.accessor("direction", { header: "Type", cell: ({ getValue }) => (getValue() === "outward" ? "Sale" : "Purchase") }),
  helper.accessor("total", { id: "total", header: "Total", cell: ({ getValue }) => <MoneyText value={orZero(getValue())} /> }),
  helper.accessor("outstanding", { header: "Outstanding", cell: ({ getValue }) => <MoneyText value={orZero(getValue())} /> }),
  helper.accessor("payment_status", { header: "Payment", cell: ({ getValue }) => <StatusBadge status={getValue()} /> }),
  helper.accessor("status", { header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue()} /> }),
  helper.accessor("issue_count", { header: "Issues", cell: ({ getValue, row }) => <span className={cn("tabular-nums", getValue() > 0 && "text-warning")}>{getValue() > 0 ? `${getValue()} · ${row.original.validation_status ?? ""}` : "—"}</span> }),
  helper.accessor("confidence", { id: "confidence", header: "Conf.", cell: ({ getValue }) => <span className="tabular-nums text-muted">{getValue() ?? "—"}</span> }),
  helper.accessor("due_date", { id: "due_date", header: "Due", cell: ({ getValue }) => <span className="tabular-nums">{formatDate(getValue())}</span> }),
]);

const RIGHT_ALIGNED = new Set(["total", "outstanding", "issue_count", "confidence"]);

export interface InvoiceTableProps {
  rows: InvoiceList[] | undefined;
  ordering: InvoiceOrdering;
  onOrderingChange: (ordering: InvoiceOrdering) => void;
  onSelectionChange: (ids: string[]) => void;
  /** Bumps whenever selection must be cleared (after a bulk action or page change). */
  selectionResetKey: number;
  isFetching?: boolean;
}

export function InvoiceTable({ rows, ordering, onOrderingChange, onSelectionChange, selectionResetKey, isFetching = false }: InvoiceTableProps) {
  const router = useRouter();
  const table = useTable({
    features,
    columns,
    data: rows ?? EMPTY_ROWS,
    getRowId: (row) => row.id,
    enableRowSelection: true,
  });
  const selectedIds = table.getSelectedRowIds();
  const selectionKey = selectedIds.join("|");

  useEffect(() => onSelectionChange(selectionKey === "" ? [] : selectionKey.split("|")), [selectionKey, onSelectionChange]);
  useEffect(() => table.resetRowSelection(true), [selectionResetKey, table]);

  const sortableById = useMemo(() => new Map(SORTABLE_COLUMNS.map((column) => [column.id, column.field])), []);

  return (
    <div className={cn("rounded-card border border-border bg-surface transition-opacity", isFetching && "opacity-70")} aria-busy={isFetching}>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((group) => (
            <TableRow key={group.id}>
              {group.headers.map((header) => {
                const field = sortableById.get(header.column.id);
                const isSortedDesc = field ? ordering === `-${field}` : false;
                const isSortedAsc = field ? ordering === field : false;
                return (
                  <TableHead key={header.id} className={cn(RIGHT_ALIGNED.has(header.column.id) && "text-right")}>
                    {field ? (
                      <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => onOrderingChange(nextOrdering(ordering, field))} aria-sort={isSortedDesc ? "descending" : isSortedAsc ? "ascending" : "none"}>
                        <table.FlexRender header={header} />
                        {isSortedDesc && <ArrowDown size={12} strokeWidth={ICON_STROKE} aria-hidden />}
                        {isSortedAsc && <ArrowUp size={12} strokeWidth={ICON_STROKE} aria-hidden />}
                      </button>
                    ) : (
                      <table.FlexRender header={header} />
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id} data-state={row.getIsSelected() ? "selected" : undefined} className="cursor-pointer" onClick={() => router.push(`/invoices/${row.original.id}`)}>
              {row.getAllCells().map((cell) => (
                <TableCell key={cell.id} className={cn(RIGHT_ALIGNED.has(cell.column.id) && "text-right")}>
                  <table.FlexRender cell={cell} />
                </TableCell>
              ))}
            </TableRow>
          ))}
          {rows && rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={columns.length} className="py-10 text-center text-muted">
                No invoices match these filters.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
