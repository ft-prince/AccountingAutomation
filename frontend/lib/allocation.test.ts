import { describe, expect, test } from "vitest";
import { allocationRemainder, allocationsToSubmit, isOverAllocated, suggestedAllocation } from "./allocation";

describe("allocation arithmetic", () => {
  test("remainder is exact to the paisa", () => {
    expect(allocationRemainder("1000.00", [{ invoice: "a", amount: "333.33" }, { invoice: "b", amount: "666.67" }])).toBe("0.00");
    expect(allocationRemainder("0.30", [{ invoice: "a", amount: "0.10" }, { invoice: "b", amount: "0.20" }])).toBe("0.00");
  });

  test("over-allocation is detected and blank inputs count as zero", () => {
    expect(isOverAllocated("100", [{ invoice: "a", amount: "60" }, { invoice: "b", amount: "40.01" }])).toBe(true);
    expect(isOverAllocated("100", [{ invoice: "a", amount: "" }, { invoice: "b", amount: "100" }])).toBe(false);
  });

  test("suggested allocation caps at the smaller of outstanding and remainder", () => {
    expect(suggestedAllocation("500.00", "120.50")).toBe("120.50");
    expect(suggestedAllocation("50.00", "120.50")).toBe("50.00");
    expect(suggestedAllocation("50.00", "-1.00")).toBe("0.00");
  });

  test("only positive amounts are submitted", () => {
    expect(allocationsToSubmit([{ invoice: "a", amount: "" }, { invoice: "b", amount: "12.5" }])).toEqual([{ invoice: "b", amount: "12.50" }]);
  });
});
