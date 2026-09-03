import { describe, expect, test } from "vitest";
import { abbreviateINR, formatINR } from "./money";

describe("formatINR", () => {
  test("groups digits Indian-style with two decimals", () => {
    expect(formatINR("123456.7")).toBe("₹1,23,456.70");
    expect(formatINR("1234567890.5")).toBe("₹1,23,45,67,890.50");
    expect(formatINR("999")).toBe("₹999.00");
    expect(formatINR("1000")).toBe("₹1,000.00");
  });
  test("handles negatives and no-symbol", () => {
    expect(formatINR("-1234.5")).toBe("-₹1,234.50");
    expect(formatINR("1234.5", { symbol: false })).toBe("1,234.50");
  });
  test("keeps precision floats would lose", () => {
    expect(formatINR("0.1")).toBe("₹0.10");
    expect(formatINR("12345678901234.99")).toBe("₹1,23,45,67,89,01,234.99");
  });
});

describe("abbreviateINR", () => {
  test("lakh and crore above 1,00,000", () => {
    expect(abbreviateINR("250000")).toBe("₹2.5L");
    expect(abbreviateINR("100000")).toBe("₹1L");
    expect(abbreviateINR("12500000")).toBe("₹1.25Cr");
    expect(abbreviateINR("-30000000")).toBe("-₹3Cr");
  });
  test("plain format below one lakh", () => {
    expect(abbreviateINR("99999")).toBe("₹99,999.00");
  });
});
