import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import type { InvoiceDetail } from "@/lib/invoices";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: vi.fn() };
});
vi.mock("@/lib/auth", () => ({
  useUser: () => ({ data: { user: { id: "u", email: "dev@nexren.ai", full_name: "Dev" }, org: null, role: "owner", orgs: [] } }),
}));
vi.mock("./pdf-pane", () => ({ PdfPane: () => <div data-testid="pdf-pane" /> }));

import { api, ApiError } from "@/lib/api";
import { ReviewScreen } from "./review-screen";

const apiMock = vi.mocked(api);

function invoice(id: string, number: string, overrides: Partial<InvoiceDetail> = {}): InvoiceDetail {
  return {
    id,
    invoice_number: number,
    invoice_date: "2026-08-06",
    due_date: "2026-08-21",
    direction: "inward",
    party: "party-1",
    party_name: "Robu Electronics",
    supply_type: "intra",
    taxable_value: "10000.00",
    cgst: "900.00",
    sgst: "900.00",
    igst: "0.00",
    cess: "0.00",
    round_off: "0.00",
    total: "11800.00",
    amount_paid: "0.00",
    outstanding: "11800.00",
    payment_status: "unpaid",
    status: "needs_review",
    validation_status: "valid",
    confidence: "0.62",
    fy: "2026-27",
    period_month: "2026-08",
    issue_count: 0,
    created_at: "",
    updated_at: "",
    document: null as unknown as string,
    lines: [
      {
        id: `${id}-l1`,
        line_no: 1,
        description: "Sensor order",
        hsn_sac: "8543",
        quantity: "1.000",
        uom: "",
        unit_price: "10000.00",
        discount: "0.00",
        taxable_value: "10000.00",
        rate: "18.00",
        cess_rate: "0.00",
        cgst: "900.00",
        sgst: "900.00",
        igst: "0.00",
        cess: "0.00",
        line_total: "11800.00",
        category: null,
        confidence: "0.99",
      },
    ],
    issues: [],
    ...overrides,
  };
}

interface Fixture {
  invoices: Record<string, InvoiceDetail>;
  confirmResponse?: (id: string) => Promise<InvoiceDetail>;
}

function installApi({ invoices, confirmResponse }: Fixture) {
  apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (path.startsWith("/api/invoices/review-queue/")) {
      return { results: Object.values(invoices), next: null, previous: null };
    }
    const confirm = /^\/api\/invoices\/([^/]+)\/confirm\/$/.exec(path);
    if (confirm) {
      const id = confirm[1];
      if (confirmResponse) return confirmResponse(id);
      return { ...invoices[id], status: "confirmed" };
    }
    const reject = /^\/api\/invoices\/([^/]+)\/reject\/$/.exec(path);
    if (reject) return { ...invoices[reject[1]], status: "rejected" };
    const detail = /^\/api\/invoices\/([^/]+)\/$/.exec(path);
    if (detail) {
      const current = invoices[detail[1]];
      if (method === "PATCH") {
        const patch = JSON.parse(String(init?.body)) as { invoice_number?: string };
        return { ...current, invoice_number: patch.invoice_number ?? current.invoice_number };
      }
      return current;
    }
    if (path.startsWith("/api/parties/")) return { id: "party-1", legal_name: "Robu Electronics", gstin: "27BDEWF7916V1ZB", state_code: "27", payment_terms_days: 15 };
    if (path.startsWith("/api/reports/")) return { rows: [{ party: "party-1", name: "Robu Electronics", "0-30": "5000.00", "31-60": "0", "61-90": "0", "90+": "0", total: "5000.00" }] };
    throw new Error(`unmocked ${method} ${path}`);
  });
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReviewScreen />
    </QueryClientProvider>,
  );
}

function calls(): string[] {
  return apiMock.mock.calls.map(([path, init]) => `${init?.method ?? "GET"} ${path}`);
}

beforeEach(() => {
  apiMock.mockReset();
  window.localStorage.clear();
});

describe("ReviewScreen", () => {
  test("loads the queue and focuses the first low-confidence field", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001"), "inv-2": invoice("inv-2", "PEND-002") } });
    renderScreen();
    const number = await screen.findByLabelText("Invoice number");
    expect(number).toHaveValue("PEND-001");
    expect(number).toHaveFocus();
    expect(number).toHaveClass("border-accent");
    expect(screen.getByTestId("queue-position")).toHaveTextContent("1 of 2 · 2 remaining");
  });

  test("Enter confirms the current invoice and advances to the next", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001"), "inv-2": invoice("inv-2", "PEND-002") } });
    renderScreen();
    await screen.findByDisplayValue("PEND-001");

    fireEvent.keyDown(window, { key: "Enter" });

    await screen.findByDisplayValue("PEND-002");
    expect(calls()).toContain("POST /api/invoices/inv-1/confirm/");
    expect(screen.getByTestId("queue-position")).toHaveTextContent("1 remaining");
  });

  test("R opens the reject dialog, but typing r in an input does not", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001") } });
    renderScreen();
    const number = await screen.findByLabelText("Invoice number");

    fireEvent.keyDown(number, { key: "r" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    number.blur();
    fireEvent.keyDown(document.body, { key: "r" });
    expect(await screen.findByRole("dialog")).toHaveTextContent("Reject invoice");
  });

  test("? opens the shortcut overlay", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001") } });
    renderScreen();
    (await screen.findByLabelText("Invoice number")).blur();

    fireEvent.keyDown(document.body, { key: "?", shiftKey: true });

    expect(await screen.findByRole("dialog")).toHaveTextContent("Keyboard shortcuts");
  });

  test("Cmd+Z undoes the last edit", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001") } });
    renderScreen();
    const number = await screen.findByLabelText("Invoice number");

    fireEvent.change(number, { target: { value: "PEND-001-X" } });
    expect(number).toHaveValue("PEND-001-X");
    fireEvent.keyDown(number, { key: "z", metaKey: true });

    expect(number).toHaveValue("PEND-001");
  });

  test("shows the reconciliation strip in danger colour when the server total differs from the client recompute", async () => {
    // Lines say 11,800.00 but the server carries a stated total of 11,818.00.
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001", { total: "11818.00", round_off: "18.00" }) } });
    renderScreen();
    await screen.findByDisplayValue("PEND-001");

    const strip = await screen.findByTestId("reconciliation-strip");
    expect(strip).toHaveClass("text-danger");
    expect(strip).toHaveTextContent("₹18.00");
  });

  test("no strip when client and server agree", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001") } });
    renderScreen();
    await screen.findByDisplayValue("PEND-001");
    expect(screen.queryByTestId("reconciliation-strip")).not.toBeInTheDocument();
  });

  test("a rejected confirm rolls the queue back and opens the confirm gate with the server's issues", async () => {
    const problemIssue = { id: "iss-1", code: "GSTIN_INVALID", severity: "error", field: "supplier_gstin", message: "Checksum failed" };
    installApi({
      invoices: { "inv-1": invoice("inv-1", "PEND-001"), "inv-2": invoice("inv-2", "PEND-002") },
      confirmResponse: async () => {
        throw new ApiError({ title: "Bad Request", status: 400, errors: { issues: [problemIssue] } });
      },
    });
    renderScreen();
    await screen.findByDisplayValue("PEND-001");

    fireEvent.keyDown(window, { key: "Enter" });

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/GSTIN_INVALID/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("PEND-001")).toBeInTheDocument();
    expect(screen.getByTestId("queue-position")).toHaveTextContent("2 remaining");
  });

  test("dirty edits are saved before confirming", async () => {
    installApi({ invoices: { "inv-1": invoice("inv-1", "PEND-001"), "inv-2": invoice("inv-2", "PEND-002") } });
    renderScreen();
    const number = await screen.findByLabelText("Invoice number");
    fireEvent.change(number, { target: { value: "PEND-001-B" } });

    await act(async () => {
      fireEvent.keyDown(number, { key: "Enter" });
    });

    await waitFor(() => expect(calls()).toContain("POST /api/invoices/inv-1/confirm/"));
    const order = calls();
    expect(order.indexOf("PATCH /api/invoices/inv-1/")).toBeLessThan(order.indexOf("POST /api/invoices/inv-1/confirm/"));
  });

  test("shows the empty state when the queue is clear", async () => {
    installApi({ invoices: {} });
    renderScreen();
    expect(await screen.findByText("Queue clear")).toBeInTheDocument();
  });
});
