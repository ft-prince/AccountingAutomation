"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { CursorPager } from "@/components/primitives/cursor-pager";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { useUser } from "@/lib/auth";
import { filtersFromSearchParams, filtersToSearchParams, type InvoiceFilters } from "@/lib/invoice-filters";
import { useInvoiceList } from "@/lib/invoice-queries";
import { canConfirmInvoices } from "@/lib/roles";
import { BulkActionBar } from "./bulk-action-bar";
import { InvoiceFiltersBar } from "./invoice-filters-bar";
import { InvoiceTable } from "./invoice-table";
import { SavedViewsMenu } from "./saved-views-menu";

export function InvoicesView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filters = useMemo(() => filtersFromSearchParams(new URLSearchParams(searchParams.toString())), [searchParams]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [resetKey, setResetKey] = useState(0);
  const { data: me } = useUser();

  const list = useInvoiceList(filters, { cursor });
  const setFilters = useCallback(
    (next: InvoiceFilters) => {
      setCursor(null);
      setResetKey((key) => key + 1);
      router.replace(`${pathname}${filtersToSearchParams(next)}`, { scroll: false });
    },
    [pathname, router],
  );
  const clearSelection = useCallback(() => setResetKey((key) => key + 1), []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="All"
        emphasis="invoices"
        description={list.data ? `${list.data.results.length} on this page · sorted by ${filters.ordering.replace("-", "").replace("__", " ")} ${filters.ordering.startsWith("-") ? "↓" : "↑"}` : "Server-side paging, sorting and filters"}
        actions={me && <SavedViewsMenu userId={me.user.id} filters={filters} onApply={setFilters} />}
      />
      <InvoiceFiltersBar filters={filters} onChange={setFilters} />
      <BulkActionBar selectedIds={selectedIds} rows={list.data?.results ?? []} filters={filters} canConfirm={canConfirmInvoices(me?.role)} onDone={clearSelection} />
      <QueryState isPending={list.isPending} error={list.error} onRetry={() => list.refetch()} skeletonClassName="h-96 w-full">
        <InvoiceTable
          rows={list.data?.results}
          ordering={filters.ordering}
          onOrderingChange={(ordering) => setFilters({ ...filters, ordering })}
          onSelectionChange={setSelectedIds}
          selectionResetKey={resetKey}
          isFetching={list.isFetching}
        />
        <CursorPager
          next={list.data?.next}
          previous={list.data?.previous}
          onCursor={(next) => {
            setCursor(next);
            clearSelection();
          }}
          isFetching={list.isFetching}
          count={list.data?.results.length}
        />
      </QueryState>
    </div>
  );
}
