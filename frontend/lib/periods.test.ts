import { describe, expect, test } from "vitest";
import { fiscalYearBounds, fiscalYearStartYear, resolvePeriod } from "./periods";

describe("fiscal year (1 Apr – 31 Mar)", () => {
  test("a date in Jan 2027 belongs to FY 2026-27 spanning 2026-04-01 to 2027-03-31", () => {
    // Arrange
    const startYear = fiscalYearStartYear("2027-01-15");
    // Act
    const bounds = fiscalYearBounds(startYear);
    // Assert
    expect(startYear).toBe(2026);
    expect(bounds).toEqual({ from: "2026-04-01", to: "2027-03-31", fy: "2026-27" });
  });

  test("1 April starts a new FY; 31 March closes the previous one", () => {
    expect(fiscalYearStartYear("2026-04-01")).toBe(2026);
    expect(fiscalYearStartYear("2026-03-31")).toBe(2025);
  });

  test("century rollover label", () => {
    expect(fiscalYearBounds(2099).fy).toBe("2099-00");
  });
});

describe("resolvePeriod", () => {
  const today = "2027-01-15";

  test("fy_to_date runs from 1 Apr 2026 to today", () => {
    expect(resolvePeriod("fy_to_date", today)).toEqual({
      from: "2026-04-01",
      to: "2027-01-15",
      fy: "2026-27",
      label: "FY2026-27 to date",
    });
  });

  test("last_fy is the full previous FY", () => {
    expect(resolvePeriod("last_fy", today)).toMatchObject({ from: "2025-04-01", to: "2026-03-31", fy: "2025-26" });
  });

  test("this_month and last_month cross the calendar year boundary", () => {
    expect(resolvePeriod("this_month", today)).toMatchObject({ from: "2027-01-01", to: "2027-01-31", fy: "2026-27" });
    expect(resolvePeriod("last_month", today)).toMatchObject({ from: "2026-12-01", to: "2026-12-31", label: "Dec 2026" });
  });

  test("this_quarter uses FY quarters (Q4 = Jan–Mar)", () => {
    expect(resolvePeriod("this_quarter", today)).toMatchObject({ from: "2027-01-01", to: "2027-03-31", label: "Q4 FY2026-27" });
    expect(resolvePeriod("this_quarter", "2026-08-10")).toMatchObject({ from: "2026-07-01", to: "2026-09-30", label: "Q2 FY2026-27" });
  });

  test("custom keeps the given bounds and rejects inverted ranges", () => {
    expect(resolvePeriod("custom", today, { from: "2026-05-01", to: "2026-05-10" })).toMatchObject({ fy: "2026-27" });
    expect(() => resolvePeriod("custom", today, { from: "2026-05-10", to: "2026-05-01" })).toThrow();
  });
});
