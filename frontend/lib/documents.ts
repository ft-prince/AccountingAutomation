"use client";

import { keepPreviousData, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Problem } from "@/lib/api";
import { buildQuery, type Paginated } from "@/lib/query";
import type { Document, DocumentStatus } from "@/lib/types";
import type { UploadOutcome } from "@/lib/upload-queue";

export const DOCUMENT_POLL_MS = 3_000;
export const UPLOAD_CONCURRENCY = 4;
const HTTP_CREATED = 201;
const HTTP_OK = 200;
const TERMINAL_STATUSES: readonly DocumentStatus[] = ["extracted", "failed", "superseded"];

export function isTerminalDocumentStatus(status: DocumentStatus | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.includes(status);
}

function csrfHeader(): Record<string, string> {
  const token = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1];
  return token ? { "X-CSRFToken": token } : {};
}

/**
 * POST /api/documents/ with XMLHttpRequest so upload progress is observable.
 * 201 → new document; 200 → an identical file already exists (`duplicate_of`).
 */
export function uploadDocument(file: File, onProgress: (percent: number) => void): Promise<UploadOutcome> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/documents/");
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    for (const [key, value] of Object.entries(csrfHeader())) xhr.setRequestHeader(key, value);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }
      if (xhr.status === HTTP_CREATED || xhr.status === HTTP_OK) {
        const doc = body as Document;
        const isDuplicate = xhr.status === HTTP_OK && Boolean(doc.duplicate_of);
        resolve({ documentId: doc.id, duplicateOf: isDuplicate ? doc.duplicate_of : undefined, status: doc.status });
        return;
      }
      const problem = (body ?? {}) as Partial<Problem>;
      reject(new ApiError({ title: problem.title ?? xhr.statusText ?? "Upload failed", status: xhr.status, ...problem }));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/**
 * Polls GET /api/documents/{id}/ every 3 s for the given ids until each reaches a terminal status.
 * TanStack Query's default refetchIntervalInBackground=false pauses polling while the tab is hidden.
 */
export function useDocumentPolling(ids: readonly string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ["documents", id],
      queryFn: () => api<Document>(`/api/documents/${id}/`),
      refetchInterval: (query: { state: { data?: Document } }) =>
        isTerminalDocumentStatus(query.state.data?.status) ? false : DOCUMENT_POLL_MS,
      refetchIntervalInBackground: false,
    })),
  });
}

export function useReextract() {
  const client = useQueryClient();
  return async (documentId: string): Promise<void> => {
    await api<unknown>(`/api/documents/${documentId}/reextract/`, { method: "POST" });
    await client.invalidateQueries({ queryKey: ["documents", documentId] });
  };
}

export interface DocumentFilters {
  status?: DocumentStatus | "";
  cursor?: string | null;
}

const DOCUMENTS_PAGE_SIZE = 50;

export function useDocuments(filters: DocumentFilters) {
  return useQuery({
    queryKey: ["documents", "list", filters],
    queryFn: () => api<Paginated<Document>>(`/api/documents/${buildQuery({ status: filters.status, cursor: filters.cursor ?? undefined, page_size: DOCUMENTS_PAGE_SIZE })}`),
    placeholderData: keepPreviousData,
  });
}

export interface SignedFile {
  url: string;
  expires_in: number;
}

/** GET /api/documents/{id}/file/ → short-lived signed URL (§12: signed URLs only). */
export function fetchSignedFileUrl(documentId: string): Promise<SignedFile> {
  return api<SignedFile>(`/api/documents/${documentId}/file/`);
}
