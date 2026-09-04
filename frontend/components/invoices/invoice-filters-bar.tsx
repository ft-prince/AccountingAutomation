"use client";

import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { PartyCombobox } from "@/components/parties/party-combobox";
import { NativeSelect } from "@/components/primitives/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCategories } from "@/lib/categories";
import { ICON_STROKE } from "@/lib/constants";
import { countActiveFilters, EMPTY_INVOICE_FILTERS, type InvoiceFilters } from "@/lib/invoice-filters";
import { fiscalYearLabel, fiscalYearStartYear, todayIso } from "@/lib/periods";

const SEARCH_DEBOUNCE_MS = 300;
const FY_HISTORY = 4;

const STATUS_OPTIONS = ["", "needs_review", "confirmed", "rejected", "duplicate"] as const;
const DIRECTION_OPTIONS = ["", "inward", "outward"] as const;
const PAYMENT_OPTIONS = ["", "unpaid", "partial", "paid", "overdue", "written_off"] as const;

function label(value: string, empty: string): string {
  return value === "" ? empty : value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function fyOptions(): string[] {
  const current = fiscalYearStartYear(todayIso());
  return Array.from({ length: FY_HISTORY }, (_, index) => fiscalYearLabel(current - index));
}

export interface InvoiceFiltersBarProps {
  filters: InvoiceFilters;
  onChange: (filters: InvoiceFilters) => void;
}

export function InvoiceFiltersBar({ filters, onChange }: InvoiceFiltersBarProps) {
  const [search, setSearch] = useState(filters.q);
  const categories = useCategories();
  const set = <K extends keyof InvoiceFilters>(key: K, value: InvoiceFilters[K]) => onChange({ ...filters, [key]: value });

  useEffect(() => setSearch(filters.q), [filters.q]);
  useEffect(() => {
    if (search === filters.q) return;
    const handle = setTimeout(() => onChange({ ...filters, q: search }), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the debounced text should trigger
  }, [search]);

  const activeCount = countActiveFilters(filters);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[16rem] flex-1">
          <Search size={16} strokeWidth={ICON_STROKE} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
          <Input aria-label="Search invoices" placeholder="Invoice number, party, IRN…" className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
        <NativeSelect aria-label="Status" value={filters.status} onChange={(event) => set("status", event.target.value as InvoiceFilters["status"])}>
          {STATUS_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {label(value, "Any status")}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect aria-label="Direction" value={filters.direction} onChange={(event) => set("direction", event.target.value as InvoiceFilters["direction"])}>
          {DIRECTION_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value === "" ? "Sales & purchases" : value === "outward" ? "Sales (outward)" : "Purchases (inward)"}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect aria-label="Payment status" value={filters.payment_status} onChange={(event) => set("payment_status", event.target.value as InvoiceFilters["payment_status"])}>
          {PAYMENT_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {label(value, "Any payment status")}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect aria-label="Financial year" value={filters.fy} onChange={(event) => set("fy", event.target.value)}>
          <option value="">Any FY</option>
          {fyOptions().map((fy) => (
            <option key={fy} value={fy}>
              FY{fy}
            </option>
          ))}
        </NativeSelect>
        <Input aria-label="Period month" type="month" className="w-40" value={filters.period} onChange={(event) => set("period", event.target.value)} />
        <PartyCombobox value={filters.party} onChange={(id) => set("party", id)} placeholder="Party" className="w-56" />
        <NativeSelect aria-label="Category" value={filters.category} onChange={(event) => set("category", event.target.value)}>
          <option value="">Any category</option>
          {(categories.data ?? []).map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input aria-label="From date" type="date" className="w-40" value={filters.from} onChange={(event) => set("from", event.target.value)} />
        <Input aria-label="To date" type="date" className="w-40" value={filters.to} onChange={(event) => set("to", event.target.value)} />
        <Input aria-label="Minimum total" inputMode="decimal" placeholder="Min ₹" className="w-28" value={filters.min} onChange={(event) => set("min", event.target.value)} />
        <Input aria-label="Maximum total" inputMode="decimal" placeholder="Max ₹" className="w-28" value={filters.max} onChange={(event) => set("max", event.target.value)} />
        {activeCount > 0 && (
          <Button variant="ghost" size="sm" onClick={() => onChange({ ...EMPTY_INVOICE_FILTERS, ordering: filters.ordering })}>
            <X strokeWidth={ICON_STROKE} aria-hidden /> Clear {activeCount} filter{activeCount === 1 ? "" : "s"}
          </Button>
        )}
      </div>
    </div>
  );
}
