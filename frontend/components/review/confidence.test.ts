import { describe, expect, test } from "vitest";
import { firstFocusTarget, isLowConfidence } from "./confidence";

describe("isLowConfidence", () => {
  test("below 0.90 is low; 0.90 and above is not; garbage is not", () => {
    expect(isLowConfidence("0.899")).toBe(true);
    expect(isLowConfidence("0.90")).toBe(false);
    expect(isLowConfidence("0.95")).toBe(false);
    expect(isLowConfidence(undefined)).toBe(false);
    expect(isLowConfidence("n/a")).toBe(false);
  });
});

describe("firstFocusTarget", () => {
  test("low invoice confidence focuses the invoice number", () => {
    expect(firstFocusTarget("0.7", ["0.99"])).toEqual({ kind: "header", field: "invoice_number" });
  });
  test("confident header but a weak line focuses that line", () => {
    expect(firstFocusTarget("0.97", ["0.99", "0.4"])).toEqual({ kind: "line", index: 1 });
  });
  test("everything confident still lands on the first field", () => {
    expect(firstFocusTarget("0.97", ["0.99"])).toEqual({ kind: "header", field: "invoice_number" });
  });
});
