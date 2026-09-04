import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";
import { ALL_SAMPLES, MODULES, SAMPLE_DIR } from "./guide";

const PUBLIC_DIR = join(__dirname, "..", "public");

describe("guide", () => {
  test("every sample file the guide offers exists on disk", () => {
    expect(ALL_SAMPLES.length).toBeGreaterThan(0);
    for (const sample of ALL_SAMPLES) {
      const path = join(PUBLIC_DIR, SAMPLE_DIR, sample.file);
      expect(existsSync(path), `missing sample: ${sample.file}`).toBe(true);
    }
  });

  test("module ids and sample filenames are unique", () => {
    const ids = MODULES.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
    const files = ALL_SAMPLES.map((s) => s.file);
    expect(new Set(files).size).toBe(files.length);
  });

  test("every module links to a route the app serves", async () => {
    const { APP_NAV } = await import("./routes");
    const hrefs = new Set(APP_NAV.map((r) => r.href));
    for (const mod of MODULES) {
      expect(hrefs.has(mod.route), `${mod.route} is not in APP_NAV`).toBe(true);
    }
  });
});
