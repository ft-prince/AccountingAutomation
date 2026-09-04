"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { UPLOAD_CONCURRENCY, isTerminalDocumentStatus, uploadDocument, useDocumentPolling, useReextract } from "@/lib/documents";
import { createUploadQueue, type UploadQueue, type UploadTask } from "@/lib/upload-queue";

const EMPTY_TASKS: readonly UploadTask[] = [];

/**
 * Binds the pure upload scheduler to XHR uploads and 3 s status polling. At most four uploads are in
 * flight, so a 200-file drop queues 196 and never blocks the main thread on network work.
 */
export function useUploadQueue() {
  const [tasks, setTasks] = useState<readonly UploadTask[]>(EMPTY_TASKS);
  const queueRef = useRef<UploadQueue | null>(null);
  if (queueRef.current === null) {
    queueRef.current = createUploadQueue({ concurrency: UPLOAD_CONCURRENCY, upload: uploadDocument, onChange: setTasks });
  }
  const queue = queueRef.current;
  const reextract = useReextract();

  const processingIds = useMemo(
    () => tasks.filter((task) => task.status === "processing" && task.documentId).map((task) => task.documentId as string),
    [tasks],
  );
  const polls = useDocumentPolling(processingIds);

  // Fold terminal document statuses back into the task list.
  useEffect(() => {
    for (const poll of polls) {
      const doc = poll.data;
      if (!doc || !isTerminalDocumentStatus(doc.status)) continue;
      const task = tasks.find((candidate) => candidate.documentId === doc.id && candidate.status === "processing");
      if (!task) continue;
      queue.update(task.id, {
        status: doc.status === "extracted" ? "extracted" : "failed",
        error: doc.status === "extracted" ? undefined : doc.error || `Document ${doc.status}`,
      });
    }
  }, [polls, tasks, queue]);

  const add = useCallback((files: readonly File[]) => queue.add(files), [queue]);

  /** Upload failures re-queue the file; extraction failures ask the server to re-extract. */
  const retry = useCallback(
    async (task: UploadTask) => {
      if (!task.documentId) {
        queue.retry(task.id);
        return;
      }
      queue.update(task.id, { status: "processing", error: undefined });
      try {
        await reextract(task.documentId);
      } catch (error) {
        queue.update(task.id, { status: "failed", error: error instanceof Error ? error.message : "Re-extract failed" });
      }
    },
    [queue, reextract],
  );

  return { tasks, add, retry };
}
