import { describe, expect, test } from "vitest";
import { backtestBadge, bandPoints, runwayLabel } from "./forecast-data";

const points = [
  { date: "2026-09-05", p10: "100.00", p50: "150.00", p90: "200.00", deterministic: "160.00" },
  { date: "2026-09-06", p10: null, p50: null, p90: null, deterministic: "170.00" },
];

describe("bandPoints", () => {
  test("keeps decimal strings for labels and numbers only for geometry", () => {
    const [first, second] = bandPoints(points);
    expect(first.band).toEqual([100, 200]);
    expect(first.p50Text).toBe("150.00");
    expect(first.deterministicText).toBe("160.00");
    expect(second.band).toBeUndefined();
    expect(second.p50).toBeUndefined();
    expect(second.deterministic).toBe(170);
  });

  test("showBands=false drops P10–P90 and P50 (insufficient history, §8.1)", () => {
    const [first] = bandPoints(points, [], false);
    expect(first.band).toBeUndefined();
    expect(first.p50).toBeUndefined();
    expect(first.deterministic).toBe(160);
  });

  test("scenario overlay joins on date and adds an overlay series", () => {
    const merged = bandPoints(points, [{ date: "2026-09-06", p10: "1", p50: "999.50", p90: "2", deterministic: "0" }]);
    expect(merged[0].overlay).toBeUndefined();
    expect(merged[1].overlay).toBe(999.5);
    expect(merged[1].overlayText).toBe("999.50");
  });
});

describe("backtestBadge thresholds (§8.7: 75–90%)", () => {
  test("inside the target range is calibrated in success", () => {
    expect(backtestBadge("0.82", 6)).toEqual({ label: "Bands calibrated · 82% coverage · 6 origins", tone: "success", isCalibrated: true });
    expect(backtestBadge("0.75").isCalibrated).toBe(true);
    expect(backtestBadge("0.90").isCalibrated).toBe(true);
  });
  test("outside the range is miscalibrated in warning", () => {
    expect(backtestBadge("0")).toEqual({ label: "Bands miscalibrated · 0% coverage", tone: "warning", isCalibrated: false });
    expect(backtestBadge("0.95").tone).toBe("warning");
    expect(backtestBadge("0.74").tone).toBe("warning");
  });
  test("no coverage yet is muted", () => {
    expect(backtestBadge(null).tone).toBe("muted");
  });
});

describe("runwayLabel", () => {
  test("date or > horizon", () => {
    expect(runwayLabel("2026-12-01")).toBe("2026-12-01");
    expect(runwayLabel(null)).toBe("> horizon");
  });
});
