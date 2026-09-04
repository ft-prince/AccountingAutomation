import { describe, expect, test } from "vitest";
import type { InvoiceDetail, InvoicePatch } from "@/lib/invoices";
import { EMPTY_FORM_STATE, formReducer, isDirty, patchesEqual, toPatch } from "./form-state";

const base: InvoicePatch = {
  invoice_number: "A-1",
  invoice_date: "2026-08-01",
  due_date: null,
  place_of_supply_state_code: "27",
  supply_type: "intra",
  is_reverse_charge: false,
  irn: "",
  has_qr: false,
  itc_eligible: true,
  notes: "",
  payment_terms: "",
  lines: [{ description: "x", hsn_sac: "", quantity: "1", uom: "", unit_price: "10", discount: "0", rate: "18", cess_rate: "0" }],
};

const invoice = {
  id: "inv-1",
  invoice_number: "A-1",
  invoice_date: "2026-08-01",
  due_date: null,
  place_of_supply_state_code: "27",
  supply_type: "intra",
  party: "p",
  lines: [{ id: "l-1", line_no: 1, description: "x", quantity: "1.000", unit_price: "10.00", discount: "0.00", rate: "18.00", cess_rate: "0.00" }],
  issues: [],
} as unknown as InvoiceDetail;

describe("patchesEqual", () => {
  test("decimal columns compare by value, text columns by string", () => {
    const normalised = { ...base, lines: [{ ...base.lines![0], quantity: "1.000", unit_price: "10.00" }] };
    expect(patchesEqual(base, normalised)).toBe(true);
    expect(patchesEqual(base, { ...base, invoice_number: "A-2" })).toBe(false);
    expect(patchesEqual(base, { ...base, lines: [] })).toBe(false);
  });
});

describe("saved action", () => {
  test("a save that matches what was sent adopts the server snapshot and is clean", () => {
    let state = formReducer(EMPTY_FORM_STATE, { type: "reset", invoice });
    state = formReducer(state, { type: "line", index: 0, column: "unit_price", value: "20" });
    const sentPatch = toPatch(state.draft);
    const fromServer = { ...invoice, lines: [{ ...invoice.lines[0], id: "l-new", unit_price: "20.00" }] } as InvoiceDetail;
    state = formReducer(state, { type: "saved", invoice: fromServer, sentPatch });
    expect(isDirty(state)).toBe(false);
    expect(state.draft.lines[0].id).toBe("l-new");
  });

  test("edits typed while the save was in flight survive and stay dirty", () => {
    let state = formReducer(EMPTY_FORM_STATE, { type: "reset", invoice });
    state = formReducer(state, { type: "line", index: 0, column: "unit_price", value: "20" });
    const sentPatch = toPatch(state.draft);
    state = formReducer(state, { type: "header", field: "notes", value: "typed later" });
    const fromServer = { ...invoice, lines: [{ ...invoice.lines[0], unit_price: "20.00" }] } as InvoiceDetail;
    state = formReducer(state, { type: "saved", invoice: fromServer, sentPatch });
    expect(state.draft.header.notes).toBe("typed later");
    expect(isDirty(state)).toBe(true);
  });

  test("a late save for another invoice is ignored", () => {
    const state = formReducer(EMPTY_FORM_STATE, { type: "reset", invoice });
    const other = { ...invoice, id: "inv-2" } as InvoiceDetail;
    expect(formReducer(state, { type: "saved", invoice: other, sentPatch: base })).toBe(state);
  });
});
