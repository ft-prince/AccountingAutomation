"use client";

import { FileText, RefreshCw } from "lucide-react";
import dynamic from "next/dynamic";
import { EmptyState } from "@/components/primitives/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useDocumentFile } from "@/lib/invoices";
import { NoDocument } from "./no-document";

const PdfViewer = dynamic(() => import("./pdf-viewer").then((module) => module.PdfViewer), {
  ssr: false,
  loading: () => <Skeleton className="m-3 h-[60vh]" />,
});

const HTTP_NOT_FOUND = 404;

export interface PdfPaneProps {
  documentId: string | null;
}

/** Left half of /review: the signed PDF for the invoice's source document. */
export function PdfPane({ documentId }: PdfPaneProps) {
  const file = useDocumentFile(documentId);

  if (documentId === null) return <NoDocument />;
  if (file.isPending) return <Skeleton className="m-3 h-[60vh]" />;
  if (file.isError && file.error instanceof ApiError && file.error.status === HTTP_NOT_FOUND) return <NoDocument />;
  if (file.isError) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon={FileText}
          title="Could not load the document"
          description={file.error.message}
          action={
            <Button variant="outline" size="sm" onClick={() => void file.refetch()}>
              <RefreshCw /> Retry
            </Button>
          }
        />
      </div>
    );
  }
  return <PdfViewer url={file.data.url} />;
}
