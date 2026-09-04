import { screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import { InvoiceEntryActions } from "./invoice-entry-actions";

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), api: apiMock }));

describe("InvoiceEntryActions role gate (§12)", () => {
  test("a viewer sees no New invoice or Import control", () => {
    // Act
    renderWithClient(<InvoiceEntryActions role="viewer" />);

    // Assert
    expect(screen.queryByRole("button", { name: /New invoice/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import CSV/ })).not.toBeInTheDocument();
  });

  test("a reviewer sees neither control either — the API allows owner and accountant only", () => {
    renderWithClient(<InvoiceEntryActions role="reviewer" />);
    expect(screen.queryByRole("button", { name: /New invoice/ })).not.toBeInTheDocument();
  });

  test.each(["owner", "accountant"])("%s sees both entry points", (role) => {
    renderWithClient(<InvoiceEntryActions role={role} />);
    expect(screen.getByRole("button", { name: /New invoice/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Import CSV/ })).toBeInTheDocument();
  });
});
