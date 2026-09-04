import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import type { InvoiceImportResult } from "@/lib/invoice-queries";
import { ImportResultPanel, InvoiceImportWizard } from "./invoice-import-wizard";

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), api: apiMock }));

// A real 207 body: two invoices created, two rows rejected.
const PARTIAL: InvoiceImportResult = {
  created: [
    { invoice_number: "IMP-001", id: "i1", total: "2360" },
    { invoice_number: "IMP-003", id: "i3", total: "47200.00" },
  ],
  errors: [
    { invoice_number: "IMP-002", row: 3, error: "invoice_date: 'BADDATE' is not a date (use YYYY-MM-DD)" },
    { invoice_number: "IMP-004", row: 6, error: "row 6: no party matches gstin='27AAPFU0939F1ZV' name='Acme'" },
  ],
  invoices: 2,
  failed: 2,
};

afterEach(() => apiMock.mockReset());

describe("ImportResultPanel", () => {
  test("renders created invoices and per-row errors from a 207 payload", () => {
    // Act
    renderWithClient(<ImportResultPanel result={PARTIAL} />);

    // Assert
    const region = screen.getByRole("region", { name: "Import result" });
    expect(within(region).getByRole("status")).toHaveTextContent("2 invoices created · 2 rows failed");
    expect(within(region).getByText("IMP-001")).toBeInTheDocument();
    expect(within(region).getByText("₹2,360.00")).toBeInTheDocument();
    expect(within(region).getByText("IMP-003")).toBeInTheDocument();
    expect(within(region).getByText("₹47,200.00")).toBeInTheDocument();
    expect(within(region).getByText(/is not a date/)).toBeInTheDocument();
    expect(within(region).getByText(/no party matches/)).toBeInTheDocument();
    expect(within(region).getByText("3")).toBeInTheDocument();
    expect(within(region).getByText("6")).toBeInTheDocument();
  });

  test("says so plainly when the import only partly succeeded", () => {
    renderWithClient(<ImportResultPanel result={PARTIAL} />);
    expect(screen.getByRole("status")).toHaveTextContent("partial import");
  });

  test("no partial warning when every row succeeded", () => {
    renderWithClient(<ImportResultPanel result={{ created: PARTIAL.created, errors: [], invoices: 2, failed: 0 }} />);
    expect(screen.getByRole("status")).toHaveTextContent("2 invoices created · 0 rows failed");
    expect(screen.queryByText(/partial import/)).not.toBeInTheDocument();
  });
});

describe("InvoiceImportWizard", () => {
  test("offers the template, posts the chosen file and shows both halves of the result", async () => {
    // Arrange
    apiMock.mockResolvedValue(PARTIAL);
    renderWithClient(<InvoiceImportWizard open onOpenChange={() => {}} />);
    expect(screen.getByRole("link", { name: /Download the CSV template/ })).toHaveAttribute("href", "/api/invoices/import-template/");

    // Act
    const file = new File(["invoice_number\nIMP-001\n"], "invoices.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/CSV file/), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Import/ }));

    // Assert
    expect(await screen.findByText("IMP-001")).toBeInTheDocument();
    expect(screen.getByText(/is not a date/)).toBeInTheDocument();
    expect(apiMock).toHaveBeenCalledWith("/api/invoices/import/", expect.objectContaining({ method: "POST" }));
    expect(apiMock.mock.calls[0][1].body).toBeInstanceOf(FormData);
  });

  test("import is disabled until a file is chosen", () => {
    apiMock.mockResolvedValue(PARTIAL);
    renderWithClient(<InvoiceImportWizard open onOpenChange={() => {}} />);
    expect(screen.getByRole("button", { name: /Import/ })).toBeDisabled();
  });
});
