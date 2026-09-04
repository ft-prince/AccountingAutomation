import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { isMissingPdfError } from "./no-document";

vi.mock("@/lib/invoices", () => ({
  useDocumentFile: (id: string | null) =>
    id === null
      ? { isPending: false, isError: false }
      : { isPending: false, isError: true, error: new ApiError({ title: "Not Found", status: id === "gone" ? 404 : 500 }), refetch: vi.fn() },
}));
vi.mock("next/dynamic", () => ({ default: () => () => <div data-testid="pdf-viewer" /> }));

import { PdfPane } from "./pdf-pane";

describe("PdfPane", () => {
  test("shows the clean No document state when the invoice has no document", () => {
    render(<PdfPane documentId={null} />);
    expect(screen.getByText("No document")).toBeInTheDocument();
  });

  test("shows the clean No document state when the signed-URL endpoint 404s", () => {
    render(<PdfPane documentId="gone" />);
    expect(screen.getByText("No document")).toBeInTheDocument();
  });

  test("other failures keep the retry state", () => {
    render(<PdfPane documentId="broken" />);
    expect(screen.getByText("Could not load the document")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});

describe("isMissingPdfError", () => {
  test("recognises pdf.js missing-file errors across versions", () => {
    expect(isMissingPdfError(Object.assign(new Error("Missing PDF"), { name: "MissingPDFException" }))).toBe(true);
    expect(isMissingPdfError(Object.assign(new Error("Unexpected server response (404)"), { status: 404, missing: true }))).toBe(true);
    expect(isMissingPdfError(new Error("Invalid PDF structure"))).toBe(false);
    expect(isMissingPdfError("nope")).toBe(false);
  });
});
