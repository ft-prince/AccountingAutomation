import { describe, expect, test } from "vitest";
import { locateIssue } from "./issue-map";

describe("locateIssue", () => {
  test("line fields resolve to index and column", () => {
    expect(locateIssue("lines[0].cgst")).toEqual({ kind: "line", index: 0, column: "cgst" });
    expect(locateIssue("lines.2.rate")).toEqual({ kind: "line", index: 2, column: "rate" });
    expect(locateIssue("lines[3]")).toEqual({ kind: "line", index: 3, column: "description" });
  });

  test("header, party, totals and unknown fields", () => {
    expect(locateIssue("irn")).toEqual({ kind: "header", field: "irn" });
    expect(locateIssue("supplier_gstin")).toEqual({ kind: "party" });
    expect(locateIssue("recipient_address")).toEqual({ kind: "party" });
    expect(locateIssue("stated_total")).toEqual({ kind: "totals" });
    expect(locateIssue("something_else")).toEqual({ kind: "general" });
    expect(locateIssue(undefined)).toEqual({ kind: "general" });
  });
});
