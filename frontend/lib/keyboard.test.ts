import { describe, expect, test } from "vitest";
import { resolveShortcut } from "./keyboard";

const input = { tagName: "INPUT" };
const textarea = { tagName: "TEXTAREA" };
const body = { tagName: "BODY" };

describe("resolveShortcut", () => {
  test("Enter on the page confirms; Enter inside an input confirms too", () => {
    expect(resolveShortcut({ key: "Enter", target: body })).toBe("confirm");
    expect(resolveShortcut({ key: "Enter", target: input })).toBe("confirm");
  });

  test("Enter inside a textarea inserts a newline, but Cmd/Ctrl+Enter always confirms", () => {
    expect(resolveShortcut({ key: "Enter", target: textarea })).toBeNull();
    expect(resolveShortcut({ key: "Enter", metaKey: true, target: textarea })).toBe("confirm");
    expect(resolveShortcut({ key: "Enter", ctrlKey: true, target: textarea })).toBe("confirm");
  });

  test("Enter on a focused button is left to the button", () => {
    expect(resolveShortcut({ key: "Enter", target: { tagName: "BUTTON" } })).toBeNull();
  });

  test("R / D / J / K / ? map to actions when not typing", () => {
    expect(resolveShortcut({ key: "r", target: body })).toBe("reject");
    expect(resolveShortcut({ key: "R", target: body })).toBe("reject");
    expect(resolveShortcut({ key: "d", target: body })).toBe("duplicate");
    expect(resolveShortcut({ key: "j", target: body })).toBe("next");
    expect(resolveShortcut({ key: "k", target: body })).toBe("previous");
    expect(resolveShortcut({ key: "?", shiftKey: true, target: body })).toBe("help");
  });

  test('typing "r" in an input does NOT reject', () => {
    expect(resolveShortcut({ key: "r", target: input })).toBeNull();
    expect(resolveShortcut({ key: "?", target: textarea })).toBeNull();
    expect(resolveShortcut({ key: "d", target: { tagName: "DIV", isContentEditable: true } })).toBeNull();
  });

  test("Cmd/Ctrl+Z undoes even while typing; Shift+Cmd+Z is not undo", () => {
    expect(resolveShortcut({ key: "z", metaKey: true, target: input })).toBe("undo");
    expect(resolveShortcut({ key: "z", ctrlKey: true, target: body })).toBe("undo");
    expect(resolveShortcut({ key: "z", metaKey: true, shiftKey: true, target: body })).toBeNull();
  });

  test("Escape resolves everywhere; Alt combos are ignored", () => {
    expect(resolveShortcut({ key: "Escape", target: textarea })).toBe("escape");
    expect(resolveShortcut({ key: "r", altKey: true, target: body })).toBeNull();
  });
});
