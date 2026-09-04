import { describe, expect, test } from "vitest";
import { formatClock, formatIsoDate, humanize } from "./format";

describe("review format helpers", () => {
  test("formatClock pads to hh:mm:ss", () => {
    expect(formatClock(new Date(2026, 8, 4, 9, 5, 7))).toBe("09:05:07");
  });
  test("formatIsoDate renders day-month-year and tolerates junk", () => {
    expect(formatIsoDate("2026-08-06")).toBe("06 Aug 2026");
    expect(formatIsoDate(null)).toBe("—");
    expect(formatIsoDate("soon")).toBe("soon");
  });
  test("humanize replaces underscores and capitalises", () => {
    expect(humanize("needs_review")).toBe("Needs review");
  });
});
