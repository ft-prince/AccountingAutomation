"use client";

import { Upload } from "lucide-react";
import { useId, useRef, useState, type DragEvent } from "react";
import { ICON_STROKE } from "@/lib/constants";
import { cn } from "@/lib/utils";

const ACCEPTED = "application/pdf,image/png,image/jpeg";
export const MAX_FILE_BYTES = 25 * 1024 * 1024; // §12: 25 MB cap, validated server-side too

export interface DropzoneProps {
  onFiles: (files: File[]) => void;
  onRejected?: (rejected: File[]) => void;
}

export function Dropzone({ onFiles, onRejected }: DropzoneProps) {
  const [isOver, setIsOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

  const accept = (list: FileList | null) => {
    if (!list) return;
    const files = Array.from(list);
    const accepted = files.filter((file) => file.size <= MAX_FILE_BYTES);
    const rejected = files.filter((file) => file.size > MAX_FILE_BYTES);
    if (rejected.length > 0) onRejected?.(rejected);
    if (accepted.length > 0) onFiles(accepted);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsOver(false);
    accept(event.dataTransfer.files);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload invoices"
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setIsOver(true);
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={handleDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-card border border-dashed px-6 py-14 text-center transition-colors duration-150",
        isOver ? "border-accent bg-surface" : "border-border hover:border-muted",
      )}
    >
      <Upload size={28} strokeWidth={ICON_STROKE} className={cn(isOver ? "text-accent" : "text-muted")} aria-hidden />
      <p className="mt-4 font-semibold">Drop invoices here</p>
      <p className="mt-1 text-sm text-muted">PDF, PNG or JPEG · up to 25 MB each · hundreds at a time</p>
      <input id={inputId} ref={inputRef} type="file" multiple accept={ACCEPTED} className="sr-only" onChange={(event) => {
        accept(event.target.files);
        event.target.value = "";
      }} />
    </div>
  );
}
