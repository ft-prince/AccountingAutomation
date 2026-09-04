import { describe, expect, test } from "vitest";
import type { InvoiceDetail } from "@/lib/invoices";
import { EMPTY_FORM_STATE, formReducer, isDirty, toPatch } from "./form-state";
import { currentId, EMPTY_QUEUE, queueReducer } from "./queue-state";

const invoice = {
  id: "inv-1",
  invoice_number: "A-1",
  invoice_date: "2026-08-01",
  due_date: null,
  direction: "inward",
  party: "p-1",
  party_name: "Acme",
  supply_type: "intra",
  outstanding: "0",
  fy: "2026-27",
  period_month: "2026-08",
  issue_count: 0,
  created_at: "",
  updated_at: "",
  document: "doc-1",
  lines: [
    { id: "l-2", line_no: 2, description: "second", quantity: "1", unit_price: "5", discount: "0", rate: "18", cess_rate: "0" },
    { id: "l-1", line_no: 1, description: "first", quantity: "2", unit_price: "10", discount: "0", rate: "18", cess_rate: "0" },
  ],
  issues: [],
} as unknown as InvoiceDetail;

describe("formReducer", () => {
  test("reset orders lines by line_no and is clean", () => {
    const state = formReducer(EMPTY_FORM_STATE, { type: "reset", invoice });
    expect(state.draft.lines.map((l) => l.description)).toEqual(["first", "second"]);
    expect(isDirty(state)).toBe(false);
  });

  test("edits are dirty and Cmd+Z restores the whole run of edits to one field", () => {
    let state = formReducer(EMPTY_FORM_STATE, { type: "reset", invoice });
    state = formReducer(state, { type: "header", field: "invoice_number", value: "A-" });
    state = formReducer(state, { type: "header", field: "invoice_number", value: "A-12" });
    state = formReducer(state, { type: "line", index: 0, column: "unit_price", value: "11" });
    expect(isDirty(state)).toBe(true);
    expect(state.undo).toHaveLength(2);

    state = formReducer(state, { type: "undo" });
    expect(state.draft.lines[0].unit_price).toBe("10");
    expect(state.draft.header.invoice_number).toBe("A-12");
    state = formReducer(state, { type: "undo" });
    expect(state.draft.header.invoice_number).toBe("A-1");
    expect(isDirty(state)).toBe(false);
    expect(formReducer(state, { type: "undo" })).toBe(state);
  });

  test("add/remove lines and the PATCH body sends strings only", () => {
    let state = formReducer(EMPTY_FORM_STATE, { type: "reset", invoice });
    state = formReducer(state, { type: "addLine" });
    expect(state.draft.lines).toHaveLength(3);
    state = formReducer(state, { type: "removeLine", index: 0 });
    const patch = toPatch(state.draft);
    expect(patch.lines).toHaveLength(2);
    expect(patch.lines?.[1]).toEqual({ description: "", hsn_sac: "", quantity: "1", uom: "", unit_price: "0", discount: "0", rate: "0", cess_rate: "0" });
    expect(patch.due_date).toBeNull();
  });
});

describe("queueReducer", () => {
  test("markDone advances past done items and unmarkDone returns to the item", () => {
    let state = queueReducer(EMPTY_QUEUE, { type: "ids", ids: ["a", "b", "c"] });
    expect(currentId(state)).toBe("a");
    state = queueReducer(state, { type: "markDone", id: "a" });
    expect(currentId(state)).toBe("b");
    state = queueReducer(state, { type: "next" });
    expect(currentId(state)).toBe("c");
    state = queueReducer(state, { type: "previous" });
    expect(currentId(state)).toBe("b");
    state = queueReducer(state, { type: "unmarkDone", id: "a" });
    expect(currentId(state)).toBe("a");
  });

  test("marking the last item done leaves the queue empty", () => {
    let state = queueReducer(EMPTY_QUEUE, { type: "ids", ids: ["a"] });
    state = queueReducer(state, { type: "markDone", id: "a" });
    expect(currentId(state)).toBeNull();
  });
});
