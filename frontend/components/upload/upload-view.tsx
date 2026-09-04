"use client";

import { PageHeader } from "@/components/primitives/page-header";
import { toast } from "@/hooks/use-toast";
import { Dropzone } from "./dropzone";
import { RecentDocuments } from "./recent-documents";
import { UploadList, UploadSummary } from "./upload-list";
import { useUploadQueue } from "./use-upload-queue";

export function UploadView() {
  const { tasks, add, retry } = useUploadQueue();
  return (
    <div className="space-y-8">
      <PageHeader title="Upload" emphasis="invoices" description="Files are extracted in the background; polling pauses while this tab is hidden." />
      <Dropzone
        onFiles={add}
        onRejected={(rejected) =>
          toast({ variant: "destructive", title: `${rejected.length} file${rejected.length === 1 ? "" : "s"} over 25 MB skipped`, description: rejected.map((file) => file.name).join(", ") })
        }
      />
      {tasks.length > 0 && (
        <section className="space-y-3" aria-label="This session">
          <UploadSummary tasks={tasks} />
          <UploadList tasks={tasks} onRetry={retry} />
        </section>
      )}
      <RecentDocuments />
    </div>
  );
}
