import { describe, expect, test } from "vitest";
import { addLine, draftErrors, emptyDraft, removeLine, setLineValue, supplyTypeFor, toCreateBody } from "@/lib/invoice-draft";

const TODAY = "2026-09-04";

describe("supplyTypeFor (§3.2)", () => {
  test("same supplier and place-of-supply state is intra-state", () => {
    expect(supplyTypeFor("27", "27")).toBe("intra");
  });

  test("different states are inter-state", () => {
    expect(supplyTypeFor("27", "29")).toBe("inter");
  });

  test("an unknown state code falls back to intra-state, as the review form does", () => {
    expect(supplyTypeFor("", "29")).toBe("intra");
    expect(supplyTypeFor("27", "2")).toBe("intra");
  });
});

describe("draftErrors", () => {
  test("blocks a draft with no lines", () => {
    // Arrange
    const draft = { ...emptyDraft(TODAY), party: "p1", invoice_number: "INV-1", lines: [] };

    // Act
    const errors = draftErrors(draft);

    // Assert
    expect(errors).toContain("Add at least one line item.");
  });

  test("blocks a missing party, number, bad date and bad state code", () => {
    const draft = { ...emptyDraft(TODAY), invoice_date: "15/08/2026", place_of_supply_state_code: "2A" };
    expect(draftErrors(draft)).toEqual([
      "Choose a party.",
      "Invoice number is required.",
      "Invoice date must be a date.",
      "Place of supply is a two-digit state code (§3.1).",
    ]);
  });

  test("names the line and column when a numeric cell is not a number", () => {
    const draft = setLineValue({ ...emptyDraft(TODAY), party: "p1", invoice_number: "INV-1" }, 0, "unit_price", "12x");
    expect(draftErrors(draft)).toEqual(["Line 1: unit_price must be a number."]);
  });

  test("accepts a complete single-line draft", () => {
    const draft = { ...emptyDraft(TODAY), party: "p1", invoice_number: "INV-1" };
    expect(draftErrors(draft)).toEqual([]);
  });
});

describe("line editing is immutable", () => {
  test("addLine, removeLine and setLineValue return new objects", () => {
    // Arrange
    const draft = emptyDraft(TODAY);

    // Act
    const added = addLine(draft, "line-1");
    const edited = setLineValue(added, 1, "description", "Sensor");
    const removed = removeLine(edited, 0);

    // Assert
    expect(draft.lines).toHaveLength(1);
    expect(added.lines).toHaveLength(2);
    expect(added.lines[1].description).toBe("");
    expect(edited.lines[1].description).toBe("Sensor");
    expect(removed.lines).toHaveLength(1);
    expect(removed.lines[0].description).toBe("Sensor");
  });
});

describe("toCreateBody", () => {
  test("sends line strings and no totals — the server recomputes every tax figure", () => {
    // Arrange
    const draft = setLineValue({ ...emptyDraft(TODAY), party: "p1", invoice_number: " INV-1 ", place_of_supply_state_code: "27", gstin_profile: "g1" }, 0, "unit_price", "40000");

    // Act
    const body = toCreateBody(draft);

    // Assert
    expect(body.invoice_number).toBe("INV-1");
    expect(body.due_date).toBeNull();
    expect(body.gstin_profile).toBe("g1");
    expect(body.place_of_supply_state_code).toBe("27");
    expect(body.currency).toBe("INR");
    expect(body.lines).toEqual([{ description: "", hsn_sac: "", quantity: "1", uom: "nos", unit_price: "40000", discount: "0", rate: "18", cess_rate: "0" }]);
    expect(Object.keys(body)).not.toContain("total");
    expect(Object.keys(body)).not.toContain("taxable_value");
  });

  test("omits the optional GSTIN profile and place of supply when unset", () => {
    const body = toCreateBody({ ...emptyDraft(TODAY), party: "p1", invoice_number: "INV-2" });
    expect(body).not.toHaveProperty("gstin_profile");
    expect(body).not.toHaveProperty("place_of_supply_state_code");
  });
});
