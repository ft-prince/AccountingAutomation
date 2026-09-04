"use client";

// Client-only react-pdf viewer; loaded through next/dynamic (ssr: false) from pdf-pane.tsx
// because pdf.js touches DOM globals at import time.
import { Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";
import { isMissingPdfError, NoDocument } from "./no-document";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const PAGE_GAP_PX = 12;

export interface PdfViewerProps {
  url: string;
}

export function PdfViewer({ url }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isMissing, setIsMissing] = useState(false);

  useEffect(() => {
    setError(null);
    setIsMissing(false);
    setPageCount(0);
  }, [url]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const measure = () => setWidth(node.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const step = useCallback((direction: 1 | -1) => {
    setZoom((current) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, current + direction * ZOOM_STEP)));
  }, []);

  if (isMissing) return <NoDocument />;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5 text-xs text-muted">
        <span className="tabular-nums">{pageCount > 0 ? `${pageCount} page${pageCount === 1 ? "" : "s"}` : "Loading…"}</span>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Zoom out" onClick={() => step(-1)} disabled={zoom <= ZOOM_MIN}>
            <Minus size={ICON_SIZE} strokeWidth={ICON_STROKE} />
          </Button>
          <span className="w-10 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
          <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Zoom in" onClick={() => step(1)} disabled={zoom >= ZOOM_MAX}>
            <Plus size={ICON_SIZE} strokeWidth={ICON_STROKE} />
          </Button>
        </div>
      </div>
      <div ref={containerRef} className="min-h-0 flex-1 overflow-auto bg-background p-3">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : (
          <Document
            file={url}
            loading={<Skeleton className="h-[60vh] w-full" />}
            onLoadSuccess={(pdf) => setPageCount(pdf.numPages)}
            onLoadError={(loadError) => (isMissingPdfError(loadError) ? setIsMissing(true) : setError(`Could not render the PDF: ${loadError.message}`))}
          >
            {width > 0 &&
              Array.from({ length: pageCount }, (_, index) => (
                <div key={index} style={{ marginBottom: PAGE_GAP_PX }} className="border border-border bg-surface">
                  <Page pageNumber={index + 1} width={(width - 2 * PAGE_GAP_PX) * zoom} renderTextLayer={false} renderAnnotationLayer={false} />
                </div>
              ))}
          </Document>
        )}
      </div>
    </div>
  );
}
