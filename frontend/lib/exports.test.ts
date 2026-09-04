import { describe, expect, test } from "vitest";
import { csvExportUrl, gstr1ExportUrl, gstr3bExportUrl, toGstPeriod } from "./exports";

describe("exports", () => {
  test("toGstPeriod formats MMYYYY", () => {
    expect(toGstPeriod("2026-08-15")).toBe("082026");
  });

  test("toGstPeriod rejects non-ISO input", () => {
    expect(() => toGstPeriod("15/08/2026")).toThrow();
  });

  test("builds export urls", () => {
    expect(gstr1ExportUrl("082026")).toBe("/api/exports/gstr1?period=082026");
    expect(gstr3bExportUrl("082026")).toBe("/api/exports/gstr3b?period=082026");
    expect(csvExportUrl("tally")).toBe("/api/exports/csv?type=tally");
    expect(csvExportUrl("raw", { from: "2026-04-01", to: "2026-04-30" })).toBe("/api/exports/csv?type=raw&from=2026-04-01&to=2026-04-30");
  });
});
