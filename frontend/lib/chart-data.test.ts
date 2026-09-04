import { describe, expect, test } from "vitest";
import { donutSlices, pnlPoints, toChartNumber } from "./chart-data";

describe("donutSlices", () => {
  test("keeps at most five named slices and folds the rest into Other with an exact decimal sum", () => {
    const rows = Array.from({ length: 8 }, (_, index) => ({ category: `C${index}`, amount: `${(8 - index) * 100}.10` }));
    const slices = donutSlices(rows);
    expect(slices).toHaveLength(6);
    expect(slices.map((slice) => slice.name)).toEqual(["C0", "C1", "C2", "C3", "C4", "Other"]);
    expect(slices[5].amount).toBe("600.30");
  });

  test("drops zero rows and returns fewer than five slices without an Other", () => {
    expect(donutSlices([{ category: "Rent", amount: "10" }, { category: "Zero", amount: "0" }])).toEqual([{ name: "Rent", amount: "10", value: 10 }]);
  });
});

describe("pnlPoints", () => {
  test("adds cogs and opex as a decimal string and keeps the originals for tooltips", () => {
    const [point] = pnlPoints([{ month: "2026-04", revenue: "100.10", cogs: "0.20", opex: "0.10", net: "99.80" }]);
    expect(point.expensesText).toBe("0.30");
    expect(point.revenueText).toBe("100.10");
    expect(point.revenue).toBe(100.1);
  });
});

test("toChartNumber treats missing as zero", () => {
  expect(toChartNumber(undefined)).toBe(0);
});
