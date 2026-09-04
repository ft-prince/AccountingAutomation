import { describe, expect, test } from "vitest";
import { acknowledgedFlags, canApproveDraft, canReview, canSendDraft, priorityTone, slaCountdown, unacknowledgedFlags } from "./mail-review";

const base = { status: "pending_review" as const, guardrail_flags: ["quotes_a_price", "party_unresolved"], acknowledged_flags: [] as unknown };

describe("guardrail gates (§6.5)", () => {
  test("unacknowledged = guardrail_flags − acknowledged flags", () => {
    const draft = { ...base, acknowledged_flags: [{ reviewer: "u1", flag: "quotes_a_price", at: "2026-09-04T10:00:00Z" }] };
    expect(unacknowledgedFlags(draft)).toEqual(["party_unresolved"]);
  });

  test("malformed acknowledged entries are ignored, never trusted", () => {
    expect(acknowledgedFlags([{ flag: "x" }, "junk", null, { reviewer: 1 }])).toEqual([{ reviewer: "", flag: "x", at: "" }]);
    expect(acknowledgedFlags("not-a-list")).toEqual([]);
  });

  test("approve is blocked while any flag is unacknowledged, even for an owner", () => {
    expect(canApproveDraft("owner", base)).toBe(false);
    const cleared = { ...base, acknowledged_flags: base.guardrail_flags.map((flag) => ({ reviewer: "u", flag, at: "" })) };
    expect(canApproveDraft("owner", cleared)).toBe(true);
    expect(canApproveDraft("reviewer", cleared)).toBe(true);
  });

  test("viewer can never approve or send", () => {
    const clean = { status: "approved" as const, guardrail_flags: [], acknowledged_flags: [] };
    expect(canReview("viewer")).toBe(false);
    expect(canApproveDraft("viewer", { ...clean, status: "pending_review" })).toBe(false);
    expect(canSendDraft("viewer", clean)).toBe(false);
    expect(canSendDraft("accountant", clean)).toBe(true);
  });

  test("send requires an approved status", () => {
    expect(canSendDraft("owner", { status: "pending_review", guardrail_flags: [], acknowledged_flags: [] })).toBe(false);
    expect(canSendDraft("owner", { status: "edited_approved", guardrail_flags: [], acknowledged_flags: [] })).toBe(true);
  });
});

describe("slaCountdown", () => {
  const now = "2026-09-04T10:00:00Z";
  test("future due dates count down; under 4h is a warning", () => {
    expect(slaCountdown("2026-09-05T12:30:00Z", now)).toEqual({ label: "1d 2h left", tone: "muted", isBreached: false });
    expect(slaCountdown("2026-09-04T11:15:00Z", now)).toEqual({ label: "1h 15m left", tone: "warning", isBreached: false });
  });
  test("past due dates are breached in danger", () => {
    expect(slaCountdown("2026-09-04T09:30:00Z", now)).toEqual({ label: "overdue by 30m", tone: "danger", isBreached: true });
  });
  test("missing or invalid input yields null", () => {
    expect(slaCountdown(null, now)).toBeNull();
    expect(slaCountdown("nope", now)).toBeNull();
  });
});

describe("priorityTone", () => {
  test("only urgent/high carry semantic colour (§9)", () => {
    expect(priorityTone("urgent")).toBe("danger");
    expect(priorityTone("high")).toBe("warning");
    expect(priorityTone("normal")).toBe("muted");
    expect(priorityTone("low")).toBe("muted");
  });
});
