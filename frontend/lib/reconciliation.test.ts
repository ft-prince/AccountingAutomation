import { describe, expect, test } from "vitest";
import { groupSummaries, totalAtRisk, type GroupedMatch } from "./reconciliation";

function row(atRisk: string): GroupedMatch {
  return { at_risk: atRisk } as GroupedMatch;
}

describe("reconciliation grouping totals", () => {
  test("sums at_risk per group exactly and carries a running total in type order", () => {
    // Arrange
    const matches = {
      exact: [row("0"), row("0")],
      value_mismatch: [row("180.10"), row("0.90")],
      missing_in_2b: [row("1000.00")],
    };

    // Act
    const summaries = groupSummaries(matches);

    // Assert
    expect(summaries.map((s) => [s.type, s.count, s.atRisk, s.runningAtRisk])).toEqual([
      ["exact", 2, "0.00", "0.00"],
      ["fuzzy", 0, "0.00", "0.00"],
      ["value_mismatch", 2, "181.00", "181.00"],
      ["missing_in_books", 0, "0.00", "181.00"],
      ["missing_in_2b", 1, "1000.00", "1181.00"],
    ]);
    expect(totalAtRisk(matches)).toBe("1181.00");
  });

  test("empty input yields five zero groups", () => {
    expect(groupSummaries({})).toHaveLength(5);
    expect(totalAtRisk({})).toBe("0.00");
  });
});
