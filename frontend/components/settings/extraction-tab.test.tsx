import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import { ExtractionTab } from "./extraction-tab";

const SETTINGS = { auto_confirm: false, extraction_enabled: true, send_page_images_for_scans: false };

function mockFetch(body: unknown = SETTINGS) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }));
}

afterEach(() => vi.restoreAllMocks());

describe("ExtractionTab", () => {
  test("auto-confirm switch is disabled for non-owners", async () => {
    // Arrange
    mockFetch();

    // Act
    renderWithClient(<ExtractionTab isOwner={false} />);

    // Assert
    const autoConfirm = await screen.findByRole("switch", { name: "Auto-confirm invoices" });
    expect(autoConfirm).toBeDisabled();
    expect(autoConfirm).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("Only owners can change extraction settings.")).toBeInTheDocument();
  });

  test("owner can toggle and the PUT carries the full settings body", async () => {
    // Arrange
    const fetchSpy = mockFetch();

    // Act
    renderWithClient(<ExtractionTab isOwner />);
    const autoConfirm = await screen.findByRole("switch", { name: "Auto-confirm invoices" });
    expect(autoConfirm).toBeEnabled();
    autoConfirm.click();

    // Assert
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith("/api/settings", expect.objectContaining({ method: "PUT" })));
    const putCall = fetchSpy.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({ ...SETTINGS, auto_confirm: true });
  });

  test("warns when auto-confirm is on", async () => {
    mockFetch({ ...SETTINGS, auto_confirm: true });
    renderWithClient(<ExtractionTab isOwner />);
    expect(await screen.findByRole("status")).toHaveTextContent("Auto-confirm is ON");
  });
});
