"use client";

import { FileText, RefreshCw } from "lucide-react";
import dynamic from "next/dynamic";
import { EmptyState } from "@/components/primitives/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentFile } from "@/lib/invoices";

const PdfViewer = dynamic(() => import("./pdf-viewer").then((module) => module.PdfViewer), {
  ssr: false,
  loading: () => <Skeleton className="m-3 h-[60vh]" />,
});

export interface PdfPaneProps {
  documentId: string | null;
}

/** Left half of /review: the signed PDF for the invoice's source document. */
export function PdfPane({ documentId }: PdfPaneProps) {
  const file = useDocumentFile(documentId);

  if (documentId === null) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState icon={FileText} title="No source document" description="This invoice has no attached file, so there is nothing to render on this side." />
      </div>
    );
  }
  if (file.isPending) return <Skeleton className="m-3 h-[60vh]" />;
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
