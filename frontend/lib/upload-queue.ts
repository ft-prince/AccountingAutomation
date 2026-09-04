// Pure upload scheduler: at most `concurrency` uploads in flight, the rest queued.
// No DOM, no fetch — the caller injects `upload` so tests can drive it with fakes.

export type UploadTaskStatus = "queued" | "uploading" | "processing" | "extracted" | "failed" | "duplicate";

export interface UploadTask {
  id: string;
  file: File;
  status: UploadTaskStatus;
  /** 0–100 while uploading. */
  progress: number;
  documentId?: string;
  duplicateOf?: string;
  error?: string;
}

export interface UploadOutcome {
  documentId: string;
  duplicateOf?: string;
  /** Server status after upload; "extracted"/"failed" short-circuit polling. */
  status?: "pending" | "extracting" | "extracted" | "failed" | "superseded" | "not_invoice";
}

export interface UploadQueueOptions {
  concurrency: number;
  upload: (file: File, onProgress: (percent: number) => void) => Promise<UploadOutcome>;
  onChange: (tasks: readonly UploadTask[]) => void;
}

export interface UploadQueue {
  add: (files: readonly File[]) => void;
  retry: (taskId: string) => void;
  update: (taskId: string, patch: Partial<UploadTask>) => void;
  tasks: () => readonly UploadTask[];
}

let nextId = 0;
function taskId(): string {
  nextId += 1;
  return `upload-${nextId}`;
}

function statusAfterUpload(outcome: UploadOutcome): UploadTaskStatus {
  if (outcome.duplicateOf) return "duplicate";
  if (outcome.status === "extracted") return "extracted";
  if (outcome.status === "failed") return "failed";
  return "processing";
}

export function createUploadQueue(options: UploadQueueOptions): UploadQueue {
  let tasks: readonly UploadTask[] = [];
  let inFlight = 0;

  const publish = (next: readonly UploadTask[]) => {
    tasks = next;
    options.onChange(tasks);
  };

  const patchTask = (id: string, patch: Partial<UploadTask>) =>
    publish(tasks.map((task) => (task.id === id ? { ...task, ...patch } : task)));

  const pump = () => {
    while (inFlight < options.concurrency) {
      const next = tasks.find((task) => task.status === "queued");
      if (!next) return;
      inFlight += 1;
      patchTask(next.id, { status: "uploading", progress: 0 });
      options
        .upload(next.file, (percent) => patchTask(next.id, { progress: percent }))
        .then((outcome) =>
          patchTask(next.id, {
            status: statusAfterUpload(outcome),
            progress: 100,
            documentId: outcome.documentId,
            duplicateOf: outcome.duplicateOf,
            error: undefined,
          }),
        )
        .catch((error: unknown) =>
          patchTask(next.id, { status: "failed", error: error instanceof Error ? error.message : "Upload failed" }),
        )
        .finally(() => {
          inFlight -= 1;
          pump();
        });
    }
  };

  return {
    add: (files) => {
      const added = files.map((file): UploadTask => ({ id: taskId(), file, status: "queued", progress: 0 }));
      publish([...tasks, ...added]);
      pump();
    },
    retry: (id) => {
      patchTask(id, { status: "queued", progress: 0, error: undefined, documentId: undefined, duplicateOf: undefined });
      pump();
    },
    update: patchTask,
    tasks: () => tasks,
  };
}
