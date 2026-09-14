"use client";

import { Building2, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Checkbox } from "@/components/primitives/checkbox";
import { CursorPager } from "@/components/primitives/cursor-pager";
import { EmptyState } from "@/components/primitives/empty-state";
import { NativeSelect } from "@/components/primitives/native-select";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ICON_STROKE } from "@/lib/constants";
import { partyDisplayName, useParties } from "@/lib/parties";
import type { PartyKind } from "@/lib/types";
import { PartyDialog } from "./party-dialog";

const SEARCH_DEBOUNCE_MS = 300;

export function PartiesView() {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<PartyKind | "">("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const parties = useParties({ q, kind, includeInactive, cursor });

  useEffect(() => {
    const handle = setTimeout(() => {
      setQ(text.trim());
      setCursor(null);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [text]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Customers &"
        emphasis="vendors"
        actions={
          <Button onClick={() => setIsCreating(true)}>
            <Plus strokeWidth={ICON_STROKE} aria-hidden /> New party
          </Button>
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[10rem] flex-1">
          <Search size={16} strokeWidth={ICON_STROKE} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
          <Input aria-label="Search parties" placeholder="Name, GSTIN, email…" className="pl-9" value={text} onChange={(event) => setText(event.target.value)} />
        </div>
        <NativeSelect aria-label="Kind" value={kind} onChange={(event) => {
          setKind(event.target.value as PartyKind | "");
          setCursor(null);
        }}>
          <option value="">Customers & vendors</option>
          <option value="customer">Customers</option>
          <option value="vendor">Vendors</option>
          <option value="both">Both</option>
        </NativeSelect>
        <label className="flex items-center gap-2 text-sm text-muted">
          <Checkbox checked={includeInactive} onChange={(event) => {
            setIncludeInactive(event.target.checked);
            setCursor(null);
          }} /> Include inactive
        </label>
      </div>
      <QueryState isPending={parties.isPending} error={parties.error} onRetry={() => parties.refetch()} skeletonClassName="h-80 w-full">
        {parties.data && parties.data.results.length === 0 ? (
          <EmptyState icon={Building2} title="No parties match" description="Parties are created automatically from extracted invoices, or add one now." action={<Button onClick={() => setIsCreating(true)}>New party</Button>} />
        ) : (
          <div className="rounded-card border border-border bg-surface">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>GSTIN</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead className="text-right">Terms</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {parties.data?.results.map((party) => (
                  <TableRow key={party.id}>
                    <TableCell>
                      <Link href={`/parties/${party.id}`} className="font-medium hover:text-accent">
                        {partyDisplayName(party)}
                      </Link>
                      {party.display_name && party.display_name !== party.legal_name && <span className="block text-xs text-muted">{party.legal_name}</span>}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={party.kind} tone={party.kind === "customer" ? "success" : party.kind === "vendor" ? "info" : "muted"} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">{party.gstin || "—"}</TableCell>
                    <TableCell className="tabular-nums">{party.state_code || "—"}</TableCell>
                    <TableCell className="max-w-[14rem] truncate text-muted">{party.primary_email || "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{party.payment_terms_days ?? "—"} d</TableCell>
                    <TableCell>{party.is_active === false && <StatusBadge status="inactive" tone="muted" label="Inactive" />}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="border-t border-border px-4 py-2">
              <CursorPager next={parties.data?.next} previous={parties.data?.previous} onCursor={setCursor} isFetching={parties.isFetching} count={parties.data?.results.length} />
            </div>
          </div>
        )}
      </QueryState>
      {isCreating && <PartyDialog party={null} open onOpenChange={setIsCreating} />}
    </div>
  );
}
