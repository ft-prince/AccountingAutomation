import { describe, expect, test } from "vitest";
import { computeInvoice, computeLine, computeTotals, sameAmount, toBig } from "./recompute";

describe("computeLine", () => {
  test("intra 18% on 10000 → cgst 900 / sgst 900 / igst 0, line total 11800", () => {
    const line = computeLine({ quantity: "1", unit_price: "10000", discount: "0", rate: "18", cess_rate: "0" }, "intra");
    expect(line).toEqual({ taxable_value: "10000.00", cgst: "900.00", sgst: "900.00", igst: "0.00", cess: "0.00", line_total: "11800.00" });
  });

  test("intra 5% on 1234.56 → 30.86 / 30.86 (each head rounded independently, HALF_UP)", () => {
    const line = computeLine({ quantity: "1", unit_price: "1234.56", discount: "0", rate: "5", cess_rate: "0" }, "intra");
    expect(line.cgst).toBe("30.86");
    expect(line.sgst).toBe("30.86");
    expect(line.igst).toBe("0.00");
    expect(line.line_total).toBe("1296.28");
  });

  test("inter-state puts the full rate on IGST; export/sez/import behave the same", () => {
    const input = { quantity: "2", unit_price: "500", discount: "100", rate: "18", cess_rate: "0" };
    for (const supply of ["inter", "export", "sez", "import"] as const) {
      const line = computeLine(input, supply);
      expect(line.taxable_value).toBe("900.00");
      expect(line.igst).toBe("162.00");
      expect(line.cgst).toBe("0.00");
      expect(line.sgst).toBe("0.00");
      expect(line.line_total).toBe("1062.00");
    }
  });

  test("cess is round(taxable×cess_rate/100, 2) and joins the line total", () => {
    const line = computeLine({ quantity: "3", unit_price: "333.33", discount: "0", rate: "28", cess_rate: "12" }, "intra");
    expect(line.taxable_value).toBe("999.99");
    expect(line.cgst).toBe("140.00"); // 139.9986 → 140.00
    expect(line.cess).toBe("120.00"); // 119.9988 → 120.00
    expect(line.line_total).toBe("1399.99");
  });

  test("never uses Number: 0.1 + 0.2 style inputs stay exact", () => {
    const line = computeLine({ quantity: "3", unit_price: "0.1", discount: "0", rate: "0", cess_rate: "0" }, "intra");
    expect(line.taxable_value).toBe("0.30");
  });

  test("half-typed inputs are tolerated during editing", () => {
    expect(toBig("12.").toString()).toBe("12");
    expect(toBig("").toString()).toBe("0");
    expect(toBig("abc").toString()).toBe("0");
    expect(toBig("-").toString()).toBe("0");
  });
});

describe("computeTotals", () => {
  test("three lines needing round_off: total rounds to the rupee and the delta is stored", () => {
    const { lines, totals } = computeInvoice(
      [
        { quantity: "1", unit_price: "1234.56", discount: "0", rate: "5", cess_rate: "0" }, // 1296.28
        { quantity: "1", unit_price: "99.99", discount: "0", rate: "18", cess_rate: "0" }, // 117.99
        { quantity: "2", unit_price: "10.15", discount: "0", rate: "12", cess_rate: "0" }, // 22.74
      ],
      "intra",
    );
    expect(lines.map((line) => line.line_total)).toEqual(["1296.28", "117.99", "22.74"]);
    // exact 1437.01 → 1437, round_off −0.01
    expect(totals.total).toBe("1437.00");
    expect(totals.round_off).toBe("-0.01");
    expect(totals.taxable_value).toBe("1354.85");
    expect(totals.cgst).toBe("41.08"); // 30.86 + 9.00 + 1.22
    expect(totals.sgst).toBe("41.08");
  });

  test("x.50 rounds up (HALF_UP) with a +0.50 round_off, mirroring quantize_rupee", () => {
    const totals = computeTotals([
      { taxable_value: "10.50", cgst: "0.00", sgst: "0.00", igst: "0.00", cess: "0.00", line_total: "10.50" },
    ]);
    expect(totals.total).toBe("11.00");
    expect(totals.round_off).toBe("0.50");
  });

  test("empty invoice is all zeros", () => {
    expect(computeTotals([])).toEqual({ taxable_value: "0.00", cgst: "0.00", sgst: "0.00", igst: "0.00", cess: "0.00", round_off: "0.00", total: "0.00" });
  });
});

describe("sameAmount", () => {
  test("compares by value, not by string", () => {
    expect(sameAmount("900", "900.00")).toBe(true);
    expect(sameAmount("900.01", "900.00")).toBe(false);
    expect(sameAmount(undefined, "1")).toBe(false);
  });
});
