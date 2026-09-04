"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { formatBytes } from "@/lib/format";
import type { UploadTask, UploadTaskStatus } from "@/lib/upload-queue";

const STATUS_LABEL: Record<UploadTaskStatus, string> = {
  queued: "Queued",
  uploading: "Uploading",
  processing: "Extracting",
  extracted: "Extracted",
  failed: "Failed",
  duplicate: "Duplicate",
};

export function UploadSummary({ tasks }: { tasks: readonly UploadTask[] }) {
  const count = (status: UploadTaskStatus) => tasks.filter((task) => task.status === status).length;
  const inProgress = count("queued") + count("uploading") + count("processing");
  return (
    <p className="text-sm text-muted tabular-nums" aria-live="polite">
      {tasks.length} file{tasks.length === 1 ? "" : "s"} · {inProgress} in progress · {count("extracted")} extracted · {count("duplicate")} duplicate · {count("failed")} failed
    </p>
  );
}

export function UploadList({ tasks, onRetry }: { tasks: readonly UploadTask[]; onRetry: (task: UploadTask) => void }) {
  if (tasks.length === 0) return null;
  return (
    <ul className="divide-y divide-border rounded-card border border-border bg-surface" aria-label="Uploads">
      {tasks.map((task) => (
        <li key={task.id} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm">{task.file.name}</p>
            <p className="text-xs text-muted">
              {formatBytes(task.file.size)}
              {task.status === "duplicate" && task.duplicateOf && (
                <>
                  {" "}
                  · identical to an existing document{" "}
                  <Link href={`/invoices?q=${encodeURIComponent(task.file.name)}`} className="underline underline-offset-2 hover:text-accent">
                    find it
                  </Link>
                </>
              )}
              {task.status === "failed" && task.error && <span className="text-danger"> · {task.error}</span>}
            </p>
            {(task.status === "uploading" || task.status === "processing") && (
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-secondary" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={task.progress} aria-label={`${task.file.name} upload progress`}>
                <div className="h-full rounded-full bg-accent transition-[width] duration-150" style={{ width: `${task.progress}%` }} />
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={task.status} label={STATUS_LABEL[task.status]} />
            {task.status === "failed" && (
              <Button variant="outline" size="sm" onClick={() => onRetry(task)}>
                <RotateCcw strokeWidth={ICON_STROKE} aria-hidden /> Retry
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
