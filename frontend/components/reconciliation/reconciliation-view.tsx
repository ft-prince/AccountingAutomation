"use client";

import { GitCompareArrows } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/primitives/empty-state";
import { NativeSelect } from "@/components/primitives/native-select";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { useUser } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { useBatchDetail, useBatches } from "@/lib/reconciliation";
import { ImportPanel } from "./import-panel";
import { MatchColumns } from "./match-columns";

const IMPORT_ROLES: readonly string[] = ["owner", "accountant"];

/** §11 /reconciliation — three-column 2B vs books. */
export function ReconciliationView() {
  const { data: me } = useUser();
  const canImport = IMPORT_ROLES.includes(me?.role ?? "");
  const batches = useBatches();
  const [selected, setSelected] = useState<string | null>(null);
  const batchId = selected ?? batches.data?.[0]?.id ?? null;
  const detail = useBatchDetail(batchId);

  return (
    <div className="space-y-6">
      <PageHeader
        title="GSTR-2B,"
        emphasis="reconciled"
        description="Every 2B record against the books; ITC at risk is the tax on anything not matched exactly."
        actions={
          batches.data && batches.data.length > 0 && (
            <NativeSelect aria-label="Batch" value={batchId ?? ""} onChange={(event) => setSelected(event.target.value)}>
              {batches.data.map((batch) => (
                <option key={batch.id} value={batch.id}>{batch.period} · {batch.filename} · {formatDate(batch.imported_at)}</option>
              ))}
            </NativeSelect>
          )
        }
      />
      <ImportPanel canImport={canImport} onImported={setSelected} />
      <QueryState isPending={batches.isPending} error={batches.error} onRetry={() => void batches.refetch()} skeletonClassName="h-48 w-full">
        {!batchId ? (
          <EmptyState icon={GitCompareArrows} title="No GSTR-2B imported yet" description="Import the JSON or XLSX downloaded from the GST portal to see matches, mismatches and IMS actions." />
        ) : (
          <QueryState isPending={detail.isPending} error={detail.error} onRetry={() => void detail.refetch()} skeletonClassName="h-96 w-full">
            {detail.data && <MatchColumns detail={detail.data} canEdit={canImport} />}
          </QueryState>
        )}
      </QueryState>
    </div>
  );
}
