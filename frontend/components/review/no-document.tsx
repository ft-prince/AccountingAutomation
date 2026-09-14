"use client";

import { FileText } from "lucide-react";
import { EmptyState } from "@/components/primitives/empty-state";

/** Left pane when there is nothing to render: no document row, or the stored file is gone (404). */
export function NoDocument() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState icon={FileText} title="No document" description="This invoice has no source file to show. Review it from the extracted fields alongside." />
    </div>
  );
}

const MISSING_RE = /missing|not found|404/i;

/** pdf.js reports a 404 as MissingPDFException (v4) or a ResponseException with missing=true (v5). */
export function isMissingPdfError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const withFlags = error as Error & { missing?: boolean; status?: number };
  return error.name === "MissingPDFException" || withFlags.missing === true || withFlags.status === 404 || MISSING_RE.test(error.message);
}
