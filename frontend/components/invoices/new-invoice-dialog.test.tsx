import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import { NewInvoiceDialog } from "./new-invoice-dialog";

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), api: apiMock }));

const GSTIN = { id: "g1", gstin: "27AAPFU0939F1ZV", state_code: "27", is_default: true, created_at: "2026-01-01T00:00:00Z" };
const PARTY = { id: "p1", legal_name: "Kotak Bank Charges", state_code: "27", merged_into: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };

function mockApi(overrides: Record<string, unknown> = {}) {
  apiMock.mockImplementation(async (path: string) => {
    for (const [fragment, body] of Object.entries(overrides)) {
      if (path.includes(fragment)) return body;
    }
    if (path.startsWith("/api/gstins/")) return { results: [GSTIN], next: null, previous: null };
    if (path.startsWith("/api/parties/?")) return { results: [PARTY], next: null, previous: null };
    if (path.startsWith("/api/parties/")) return PARTY;
    throw new Error(`unexpected request ${path}`);
  });
}

/** Cells of one row of the preview table, e.g. cellsOf("CGST") → ["₹3,600.00"]. */
function cellsOf(label: string): string[] {
  const region = screen.getByRole("region", { name: "Totals preview" });
  const row = within(region).getByText(label).closest("tr");
  if (!row) throw new Error(`no row for ${label}`);
  return Array.from(row.querySelectorAll("td")).slice(1).map((cell) => cell.textContent ?? "");
}

function setCell(line: number, label: string, value: string) {
  fireEvent.change(screen.getByLabelText(`Line ${line} ${label}`), { target: { value } });
}

function open() {
  return renderWithClient(<NewInvoiceDialog open onOpenChange={() => {}} />);
}

afterEach(() => apiMock.mockReset());

describe("NewInvoiceDialog tax preview (§3.2, §3.9)", () => {
  test("intra-state 18% on 40000 previews CGST 3600, SGST 3600, no IGST and a 47200 total", async () => {
    // Arrange
    mockApi();
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");
    fireEvent.change(screen.getByLabelText("Place of supply"), { target: { value: "27" } });

    // Act
    setCell(1, "Unit price", "40000");
    setCell(1, "Qty", "1");
    setCell(1, "Rate %", "18");

    // Assert
    expect(cellsOf("Taxable value")).toEqual(["₹40,000.00"]);
    expect(cellsOf("CGST")).toEqual(["₹3,600.00"]);
    expect(cellsOf("SGST")).toEqual(["₹3,600.00"]);
    expect(cellsOf("IGST")).toEqual(["₹0.00"]);
    expect(cellsOf("Total")).toEqual(["₹47,200.00"]);
  });

  test("intra-state 5% on 1234.56 halves to 30.86 each head", async () => {
    mockApi();
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");
    fireEvent.change(screen.getByLabelText("Place of supply"), { target: { value: "27" } });

    setCell(1, "Unit price", "1234.56");
    setCell(1, "Rate %", "5");

    expect(cellsOf("CGST")).toEqual(["₹30.86"]);
    expect(cellsOf("SGST")).toEqual(["₹30.86"]);
    expect(cellsOf("IGST")).toEqual(["₹0.00"]);
  });

  test("a different place of supply moves the whole rate to IGST", async () => {
    mockApi();
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");

    fireEvent.change(screen.getByLabelText("Place of supply"), { target: { value: "29" } });
    setCell(1, "Unit price", "40000");
    setCell(1, "Rate %", "18");

    expect(cellsOf("CGST")).toEqual(["₹0.00"]);
    expect(cellsOf("SGST")).toEqual(["₹0.00"]);
    expect(cellsOf("IGST")).toEqual(["₹7,200.00"]);
    expect(cellsOf("Total")).toEqual(["₹47,200.00"]);
  });

  test("adding and removing a line updates the preview", async () => {
    mockApi();
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");
    fireEvent.change(screen.getByLabelText("Place of supply"), { target: { value: "27" } });
    setCell(1, "Unit price", "40000");

    // Act — add a second line
    fireEvent.click(screen.getByRole("button", { name: "Add line" }));
    setCell(2, "Unit price", "10000");

    // Assert
    expect(cellsOf("Taxable value")).toEqual(["₹50,000.00"]);
    expect(cellsOf("CGST")).toEqual(["₹4,500.00"]);

    // Act — remove the first line
    fireEvent.click(screen.getByRole("button", { name: "Remove line 1" }));

    // Assert
    expect(cellsOf("Taxable value")).toEqual(["₹10,000.00"]);
    expect(cellsOf("CGST")).toEqual(["₹900.00"]);
  });
});

describe("NewInvoiceDialog validation and save", () => {
  test("blocks submission with zero lines", async () => {
    mockApi();
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");

    fireEvent.click(screen.getByRole("button", { name: "Remove line 1" }));

    expect(screen.getByText("Add at least one line item.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create invoice" })).toBeDisabled();
    expect(apiMock).not.toHaveBeenCalledWith("/api/invoices/", expect.anything());
  });

  test("posts no totals and shows the server's figures beside the preview", async () => {
    // Arrange
    mockApi({
      "/api/invoices/": {
        id: "i1",
        invoice_number: "MAN-1",
        status: "needs_review",
        taxable_value: "40000.00",
        cgst: "3600.00",
        sgst: "3600.00",
        igst: "0.00",
        cess: "0.00",
        round_off: "0.00",
        total: "47200.00",
      },
    });
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");
    fireEvent.change(screen.getByLabelText(/Invoice number/), { target: { value: "MAN-1" } });
    fireEvent.change(screen.getByLabelText("Place of supply"), { target: { value: "27" } });
    setCell(1, "Unit price", "40000");
    fireEvent.change(screen.getByRole("combobox", { name: "Party" }), { target: { value: "Kotak" } });
    fireEvent.click(await screen.findByRole("button", { name: /Kotak Bank Charges/ }));

    // Act
    fireEvent.click(screen.getByRole("button", { name: "Create invoice" }));

    // Assert
    await waitFor(() => expect(screen.getByText("MAN-1")).toBeInTheDocument());
    const body = JSON.parse(apiMock.mock.calls.find(([path]) => path === "/api/invoices/")?.[1].body);
    expect(body.lines).toHaveLength(1);
    expect(body).not.toHaveProperty("total");
    expect(cellsOf("Total")).toEqual(["₹47,200.00", "₹47,200.00"]);
    expect(screen.getByRole("link", { name: "Open the review queue" })).toHaveAttribute("href", "/review");
  });

  test("flags a preview that disagrees with the server in the danger colour", async () => {
    mockApi({
      "/api/invoices/": {
        id: "i2",
        invoice_number: "MAN-2",
        status: "needs_review",
        taxable_value: "40000.00",
        cgst: "3600.00",
        sgst: "3600.00",
        igst: "0.00",
        cess: "0.00",
        round_off: "0.00",
        total: "47000.00",
      },
    });
    open();
    await screen.findByDisplayValue("27AAPFU0939F1ZV · 27");
    fireEvent.change(screen.getByLabelText(/Invoice number/), { target: { value: "MAN-2" } });
    fireEvent.change(screen.getByLabelText("Place of supply"), { target: { value: "27" } });
    setCell(1, "Unit price", "40000");
    fireEvent.change(screen.getByRole("combobox", { name: "Party" }), { target: { value: "Kotak" } });
    fireEvent.click(await screen.findByRole("button", { name: /Kotak Bank Charges/ }));

    fireEvent.click(screen.getByRole("button", { name: "Create invoice" }));

    const strip = await screen.findByTestId("create-reconciliation-strip");
    expect(strip).toHaveTextContent("₹200.00");
  });
});
