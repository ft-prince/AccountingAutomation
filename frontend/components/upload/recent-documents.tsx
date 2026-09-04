"use client";

import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { CursorPager } from "@/components/primitives/cursor-pager";
import { EmptyState } from "@/components/primitives/empty-state";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FileText } from "lucide-react";
import { ICON_STROKE } from "@/lib/constants";
import { useDocuments, useReextract } from "@/lib/documents";
import { formatBytes, formatDate } from "@/lib/format";
import { toast } from "@/hooks/use-toast";
import { toastApiError } from "@/lib/toast";
import type { DocumentStatus } from "@/lib/types";

const STATUS_OPTIONS: readonly { value: DocumentStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "extracting", label: "Extracting" },
  { value: "extracted", label: "Extracted" },
  { value: "failed", label: "Failed" },
  { value: "superseded", label: "Superseded" },
];

export function RecentDocuments() {
  const [status, setStatus] = useState<DocumentStatus | "">("");
  const [cursor, setCursor] = useState<string | null>(null);
  const documents = useDocuments({ status, cursor });
  const reextract = useReextract();

  const handleReextract = async (id: string) => {
    try {
      await reextract(id);
      toast({ title: "Re-extraction queued" });
      await documents.refetch();
    } catch (error) {
      toastApiError(error, "Could not re-extract");
    }
  };

  return (
    <section className="space-y-3" aria-label="Recent documents">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Recent documents</h2>
        <NativeSelect aria-label="Document status" value={status} onChange={(event) => {
          setStatus(event.target.value as DocumentStatus | "");
          setCursor(null);
        }}>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <QueryState isPending={documents.isPending} error={documents.error} onRetry={() => documents.refetch()}>
        {documents.data && documents.data.results.length === 0 ? (
          <EmptyState icon={FileText} title="No documents yet" description="Drop invoices above to start extraction." />
        ) : (
          <div className="rounded-card border border-border bg-surface">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="text-right">Size</TableHead>
                  <TableHead className="text-right">Pages</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Attempts</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.data?.results.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="max-w-xs truncate">
                      {doc.original_filename}
                      {doc.error && <span className="block truncate text-xs text-danger">{doc.error}</span>}
                    </TableCell>
                    <TableCell className="tabular-nums">{formatDate(doc.created_at)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatBytes(doc.size_bytes)}</TableCell>
                    <TableCell className="text-right tabular-nums">{doc.page_count ?? "—"}</TableCell>
                    <TableCell>
                      <StatusBadge status={doc.duplicate_of ? "duplicate" : doc.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{doc.attempts}</TableCell>
                    <TableCell className="text-right">
                      {doc.status === "failed" && (
                        <Button variant="outline" size="sm" onClick={() => handleReextract(doc.id)}>
                          <RotateCcw strokeWidth={ICON_STROKE} aria-hidden /> Retry
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="border-t border-border px-4 py-2">
              <CursorPager next={documents.data?.next} previous={documents.data?.previous} onCursor={setCursor} isFetching={documents.isFetching} count={documents.data?.results.length} />
            </div>
          </div>
        )}
      </QueryState>
    </section>
  );
}
