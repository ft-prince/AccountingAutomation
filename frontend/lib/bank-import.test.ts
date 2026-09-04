import { describe, expect, test } from "vitest";
import { guessColumnRole, isMappingUsable, previewStatement } from "./bank-import";

describe("previewStatement", () => {
  test("parses a quoted HDFC-style CSV and guesses column roles", () => {
    const text =
      'Date,Narration,Chq./Ref.No.,Withdrawal Amt.,Deposit Amt.,Closing Balance\r\n' +
      '04/09/26,"NEFT CR-TATA STEEL, DIGITAL-INV ""0143""",N123,,"1,23,456.00","90,58,68,23.00"\r\n' +
      "05/09/26,UPI-MISC,M7,2360.00,,90735163.00\r\n";
    const preview = previewStatement(text);
    expect(preview.headers).toEqual(["Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]);
    expect(preview.rows).toHaveLength(2);
    expect(preview.rows[0][1]).toBe('NEFT CR-TATA STEEL, DIGITAL-INV "0143"');
    expect(preview.rows[0][4]).toBe("1,23,456.00");
    expect(preview.columns.map((column) => column.role)).toEqual(["date", "description", "reference", "debit", "credit", "balance"]);
    expect(isMappingUsable(preview.columns)).toBe(true);
  });

  test("limits the preview to the requested number of rows", () => {
    const text = ["Date,Amount", ...Array.from({ length: 20 }, (_, index) => `2026-09-${index + 1},1`)].join("\n");
    expect(previewStatement(text, 3).rows).toHaveLength(3);
  });

  test("a mapping without a date or amount is not usable", () => {
    expect(isMappingUsable([{ index: 0, header: "Narration", role: "description" }])).toBe(false);
    expect(guessColumnRole("Something else")).toBe("ignore");
  });
});
