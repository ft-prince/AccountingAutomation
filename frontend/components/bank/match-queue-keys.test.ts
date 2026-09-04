import { describe, expect, test } from "vitest";
import { resolveMatchQueueKey } from "./match-queue-keys";

describe("resolveMatchQueueKey", () => {
  test("J/K move, Enter/A accept, I ignores, digits pick a candidate", () => {
    expect(resolveMatchQueueKey({ key: "j" })).toBe("next");
    expect(resolveMatchQueueKey({ key: "K" })).toBe("previous");
    expect(resolveMatchQueueKey({ key: "Enter" })).toBe("accept");
    expect(resolveMatchQueueKey({ key: "a" })).toBe("accept");
    expect(resolveMatchQueueKey({ key: "i" })).toBe("ignore");
    expect(resolveMatchQueueKey({ key: "3" })).toEqual({ candidate: 2 });
    expect(resolveMatchQueueKey({ key: "0" })).toBeNull();
  });

  test("ignores keys typed into inputs or with modifiers", () => {
    expect(resolveMatchQueueKey({ key: "j", target: { tagName: "INPUT" } })).toBeNull();
    expect(resolveMatchQueueKey({ key: "j", metaKey: true })).toBeNull();
  });
});
