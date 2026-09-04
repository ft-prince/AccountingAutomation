"use client";

import { useState } from "react";
import { MoneyText } from "@/components/primitives/money-text";
import { NativeSelect } from "@/components/primitives/native-select";
import { StatusBadge, type StatusTone } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/format";
import { groupSummaries, MATCH_TYPES, useImsAction, usePatchMatch, type BatchDetail, type GroupedMatch } from "@/lib/reconciliation";
import { toastApiError } from "@/lib/toast";
import type { ImsAction, MatchType, ReconRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPE_TONE: Record<MatchType, StatusTone> = { exact: "success", fuzzy: "info", value_mismatch: "warning", missing_in_books: "danger", missing_in_2b: "warning" };
const TYPE_LABEL: Record<MatchType, string> = { exact: "Exact", fuzzy: "Fuzzy", value_mismatch: "Value mismatch", missing_in_books: "Missing in books", missing_in_2b: "Missing in 2B" };
const IMS_ACTIONS: readonly { value: ImsAction; label: string; tone: StatusTone }[] = [
  { value: "accept", label: "Accept", tone: "success" },
  { value: "reject", label: "Reject", tone: "danger" },
  { value: "pend", label: "Pend", tone: "warning" },
];

function RecordCell({ record }: { record: ReconRecord | undefined }) {
  if (!record) return <p className="text-sm text-muted">— not in 2B —</p>;
  return (
    <div className="text-sm">
      <p className="font-medium">{record.invoice_number} <span className="text-xs text-muted tabular-nums">· {formatDate(record.invoice_date)}</span></p>
      <p className="truncate text-xs text-muted">{record.supplier_name || record.supplier_gstin}</p>
      <p className="text-xs tabular-nums">value <MoneyText value={record.invoice_value} /> · tax <MoneyText value={record.tax} />{record.reverse_charge && " · RCM"}{!record.itc_available && <span className="text-danger"> · ITC blocked</span>}</p>
    </div>
  );
}

function BooksCell({ match, canEdit }: { match: GroupedMatch; canEdit: boolean }) {
  const patch = usePatchMatch();
  const [invoiceId, setInvoiceId] = useState("");
  const [isRepointing, setIsRepointing] = useState(false);
  const invoice = match.invoice as GroupedMatch["invoice"] | null;
  const repoint = () =>
    patch.mutate({ matchId: match.id, body: { invoice: invoiceId || null, match_type: invoiceId ? "manual" as MatchType : undefined } }, {
      onSuccess: () => { toast({ title: "Match updated" }); setIsRepointing(false); },
      onError: (error) => toastApiError(error, "Could not update match"),
    });
  return (
    <div className="text-sm">
      {invoice ? (
        <>
          <p className="font-medium">{invoice.invoice_number} <span className="text-xs text-muted tabular-nums">· {formatDate(invoice.invoice_date)}</span></p>
          <p className="truncate text-xs text-muted">{invoice.party_name}</p>
          <p className="text-xs tabular-nums">total <MoneyText value={invoice.total} /> · tax <MoneyText value={invoice.tax} /></p>
        </>
      ) : (
        <p className="text-muted">— not in books —</p>
      )}
      {match.match_type !== "exact" && (
        <p className="mt-1 text-xs tabular-nums">
          Δ value <MoneyText value={match.delta_value} /> · Δ tax <MoneyText value={match.delta_tax} /> · at risk <MoneyText value={match.at_risk} className="font-medium text-warning" />
        </p>
      )}
      {canEdit && (
        isRepointing ? (
          <form className="mt-2 flex gap-1" onSubmit={(event) => { event.preventDefault(); repoint(); }}>
            <input aria-label="Invoice id" placeholder="Invoice UUID (blank to clear)" value={invoiceId} onChange={(event) => setInvoiceId(event.target.value.trim())} className="h-8 flex-1 rounded-full border border-input bg-surface px-3 text-xs" />
            <Button type="submit" size="sm" variant="outline" disabled={patch.isPending}>Save</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setIsRepointing(false)}>Cancel</Button>
          </form>
        ) : (
          <Button size="sm" variant="ghost" className="mt-1 px-2" onClick={() => setIsRepointing(true)}>Re-point</Button>
        )
      )}
    </div>
  );
}

function ImsCell({ record, canEdit }: { record: ReconRecord | undefined; canEdit: boolean }) {
  const ims = useImsAction();
  if (!record) return <span className="text-xs text-muted">no 2B record</span>;
  const current = IMS_ACTIONS.find((action) => action.value === record.ims_action);
  return (
    <div className="flex flex-wrap items-center gap-1">
      {current && <StatusBadge status={current.value} tone={current.tone} label={current.label} />}
      {canEdit && IMS_ACTIONS.filter((action) => action.value !== record.ims_action).map((action) => (
        <Button key={action.value} size="sm" variant="outline" disabled={ims.isPending} onClick={() => ims.mutate({ recordId: record.id, action: action.value }, { onSuccess: () => toast({ title: `IMS: ${action.label}` }), onError: (error) => toastApiError(error, "IMS action failed") })}>
          {action.label}
        </Button>
      ))}
      {record.ims_note && <span className="w-full text-xs text-muted">{record.ims_note}</span>}
    </div>
  );
}

/** Three columns — 2B record · books · IMS action — grouped by match type with running ITC-at-risk totals. */
export function MatchColumns({ detail, canEdit }: { detail: BatchDetail; canEdit: boolean }) {
  const recordsById = new Map(detail.records.map((record) => [record.id, record]));
  const summaries = groupSummaries(detail.matches);
  const [filter, setFilter] = useState<MatchType | "">("");
  const visible = filter ? [filter] : MATCH_TYPES;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <NativeSelect aria-label="Match type" value={filter} onChange={(event) => setFilter(event.target.value as MatchType | "")}>
          <option value="">All match types</option>
          {MATCH_TYPES.map((type) => (
            <option key={type} value={type}>{TYPE_LABEL[type]}</option>
          ))}
        </NativeSelect>
        <p className="text-sm">ITC at risk <MoneyText value={detail.itc_at_risk} className="font-semibold text-warning" /></p>
        <p className="text-xs text-muted">{detail.records.length} 2B records · {Object.values(detail.matches).reduce((count, rows) => count + rows.length, 0)} matches</p>
      </div>

      {visible.map((type) => {
        const rows = detail.matches[type] ?? [];
        const summary = summaries.find((entry) => entry.type === type);
        return (
          <section key={type} aria-label={TYPE_LABEL[type]} data-match-type={type} className="rounded-card border border-border bg-surface">
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
              <span className="flex items-center gap-2">
                <StatusBadge status={type} tone={TYPE_TONE[type]} label={TYPE_LABEL[type]} />
                <span className="text-xs text-muted">{rows.length} row{rows.length === 1 ? "" : "s"}</span>
              </span>
              <span className="text-xs tabular-nums">
                group at risk <MoneyText value={summary?.atRisk ?? "0"} className="font-medium" /> · running <MoneyText value={summary?.runningAtRisk ?? "0"} data-running className="font-semibold text-warning" />
              </span>
            </header>
            {rows.length === 0 ? (
              <p className="px-4 py-3 text-xs text-muted">None.</p>
            ) : (
              <ol className="divide-y divide-border">
                <li className="grid grid-cols-3 gap-4 px-4 py-1.5 text-[11px] uppercase tracking-wide text-muted"><span>2B record</span><span>Books</span><span>IMS action</span></li>
                {rows.map((match) => {
                  const record = (match.record as GroupedMatch["record"] | null) ? recordsById.get(match.record.id) ?? match.record : undefined;
                  return (
                    <li key={match.id} className={cn("grid grid-cols-3 gap-4 px-4 py-3", match.resolved_at && "bg-secondary/40")}>
                      <RecordCell record={record} />
                      <BooksCell match={match} canEdit={canEdit} />
                      <div className="space-y-1">
                        <ImsCell record={record} canEdit={canEdit} />
                        <p className="text-xs text-muted tabular-nums">running at risk <MoneyText value={match.running_itc_at_risk} /></p>
                        {match.note && <p className="text-xs text-muted">{match.note}</p>}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        );
      })}
    </div>
  );
}
