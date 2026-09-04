import { describe, expect, test } from "vitest";
import { hasChanges, wordDiff } from "./diff";

describe("wordDiff", () => {
  test("identical text is a single equal segment", () => {
    const segments = wordDiff("Dear Sir, thanks.", "Dear Sir, thanks.");
    expect(segments).toEqual([{ op: "equal", text: "Dear Sir, thanks." }]);
    expect(hasChanges(segments)).toBe(false);
  });

  test("marks replaced words as delete + insert and keeps the rest equal", () => {
    // Arrange
    const before = "We will pay by Friday.";
    const after = "We will pay by Monday.";

    // Act
    const segments = wordDiff(before, after);

    // Assert
    expect(segments).toEqual([
      { op: "equal", text: "We will pay by " },
      { op: "delete", text: "Friday." },
      { op: "insert", text: "Monday." },
    ]);
    expect(hasChanges(segments)).toBe(true);
  });

  test("handles pure insertions and deletions at the ends", () => {
    expect(wordDiff("Hello", "Hello world")).toEqual([
      { op: "equal", text: "Hello" },
      { op: "insert", text: " world" },
    ]);
    expect(wordDiff("Hello world", "world")).toEqual([
      { op: "delete", text: "Hello " },
      { op: "equal", text: "world" },
    ]);
  });

  test("empty inputs", () => {
    expect(wordDiff("", "")).toEqual([]);
    expect(wordDiff("", "new")).toEqual([{ op: "insert", text: "new" }]);
  });
});
