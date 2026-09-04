import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import type { Draft } from "@/lib/types";
import { DraftPanel } from "./draft-panel";

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), api: apiMock }));

function draft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: "d1",
    thread: "t1",
    in_reply_to: null,
    version: 1,
    prompt_version: "v1",
    model_name: "mock",
    context_snapshot: { party: "Tata" },
    body_text: "Dear Sir, the invoice INV-1 is due.",
    body_html: "",
    proposed_attachments: [{ filename: "statement.pdf" }],
    tone: "formal",
    confidence: "0.80",
    guardrail_flags: ["quotes_a_price"],
    acknowledged_flags: [],
    status: "pending_review",
    instruction: "",
    created_by: null,
    reviewed_by: null,
    reviewed_at: null,
    reject_reason: "",
    sent_message: null,
    sent_at: null,
    edit_distance: null,
    revisions: [],
    created_at: "2026-09-04T10:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  apiMock.mockReset();
});

describe("DraftPanel review gates (§6.5–§6.6)", () => {
  test("no Approve or Send control while a guardrail flag is unacknowledged", () => {
    // Arrange / Act
    renderWithClient(<DraftPanel draft={draft()} threadId="t1" role="owner" />);

    // Assert
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^send$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 flag must be acknowledged");
    expect(screen.getByRole("button", { name: "quotes a price" })).toHaveAttribute("data-acknowledged", "false");
    expect(screen.getByText("statement.pdf", { exact: false })).toBeInTheDocument();
  });

  test("acknowledging every flag reveals Approve & send for a reviewer", () => {
    const acked = draft({ acknowledged_flags: [{ reviewer: "u1", flag: "quotes_a_price", at: "2026-09-04T10:05:00Z" }] });
    renderWithClient(<DraftPanel draft={acked} threadId="t1" role="reviewer" />);
    expect(screen.getByRole("button", { name: "quotes a price" })).toHaveAttribute("data-acknowledged", "true");
    expect(screen.getByRole("button", { name: "Approve & send" })).toBeInTheDocument();
  });

  test("clicking a flag chip posts acknowledge-flag", async () => {
    apiMock.mockResolvedValue(draft({ acknowledged_flags: [{ reviewer: "u1", flag: "quotes_a_price", at: "" }] }));
    renderWithClient(<DraftPanel draft={draft()} threadId="t1" role="owner" />);
    fireEvent.click(screen.getByRole("button", { name: "quotes a price" }));
    await vi.waitFor(() => expect(apiMock).toHaveBeenCalledTimes(1));
    expect(apiMock).toHaveBeenCalledWith("/api/mail/drafts/d1/acknowledge-flag/", expect.objectContaining({ method: "POST", body: JSON.stringify({ flag: "quotes_a_price" }) }));
  });

  test("a viewer never sees Approve, Send, Reject or the regenerate form even with no flags", () => {
    renderWithClient(<DraftPanel draft={draft({ guardrail_flags: [] })} threadId="t1" role="viewer" />);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Regenerate instruction")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Draft body")).toBeDisabled();
  });

  test("Approve & send posts approve then send", async () => {
    apiMock.mockImplementation(async (path: string) => (path.endsWith("/approve/") ? draft({ guardrail_flags: [], status: "approved" }) : draft({ guardrail_flags: [], status: "sent" })));
    renderWithClient(<DraftPanel draft={draft({ guardrail_flags: [] })} threadId="t1" role="accountant" />);
    fireEvent.click(screen.getByRole("button", { name: "Approve & send" }));
    await vi.waitFor(() => expect(apiMock).toHaveBeenCalledTimes(2));
    expect(apiMock.mock.calls[0][0]).toBe("/api/mail/drafts/d1/approve/");
    expect(apiMock.mock.calls[1][0]).toBe("/api/mail/drafts/d1/send/");
  });

  test("after send it renders the word diff between the AI draft and the sent text", () => {
    const sent = draft({ status: "sent", body_text: "Dear Sir, the invoice INV-1 is overdue.", revisions: [{ id: "r1", editor: null, before: "Dear Sir, the invoice INV-1 is due.", after: "Dear Sir, the invoice INV-1 is overdue.", created_at: "" }], edit_distance: 1 });
    renderWithClient(<DraftPanel draft={sent} threadId="t1" role="owner" />);
    const diff = screen.getByLabelText("Changes between draft and sent text");
    expect(diff.querySelector('[data-op="delete"]')).toHaveTextContent("due.");
    expect(diff.querySelector('[data-op="insert"]')).toHaveTextContent("overdue.");
    expect(screen.queryByLabelText("Draft body")).not.toBeInTheDocument();
  });
});
