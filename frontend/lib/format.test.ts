import { describe, expect, test } from "vitest";
import { timeAgo } from "./format";

describe("timeAgo", () => {
  const now = new Date("2026-09-04T12:00:00Z");
  test("buckets by minute, hour, day and falls back to the date", () => {
    expect(timeAgo(null, now)).toBe("never");
    expect(timeAgo("2026-09-04T11:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-09-04T11:45:00Z", now)).toBe("15 min ago");
    expect(timeAgo("2026-09-04T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-09-02T12:00:00Z", now)).toBe("2 d ago");
    expect(timeAgo("2026-08-01T12:00:00Z", now)).toBe("1 Aug 2026");
  });
});
