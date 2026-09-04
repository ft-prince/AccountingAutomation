import { describe, expect, test } from "vitest";
import { parseCsv, toCsv } from "./csv";

describe("parseCsv", () => {
  test("parses quoted fields containing commas, escaped quotes and newlines", () => {
    const text = 'Date,Narration,Amount\r\n"04/09/2026","NEFT, ""Tata Steel"" ref\nline2","1,23,456.00"\n05/09/2026,UPI,500';
    expect(parseCsv(text)).toEqual([
      ["Date", "Narration", "Amount"],
      ["04/09/2026", 'NEFT, "Tata Steel" ref\nline2', "1,23,456.00"],
      ["05/09/2026", "UPI", "500"],
    ]);
  });

  test("stops after the requested number of rows", () => {
    const text = Array.from({ length: 50 }, (_, index) => `${index},row`).join("\n");
    expect(parseCsv(text, 5)).toHaveLength(5);
  });
});

describe("toCsv", () => {
  test("quotes cells with commas or quotes and keeps decimal strings verbatim", () => {
    expect(toCsv(["a", "b"], [["x, y", '"q"'], ["123456.70", null]])).toBe('a,b\r\n"x, y","""q"""\r\n123456.70,');
  });
});
