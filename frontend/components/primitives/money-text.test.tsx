import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { MoneyText } from "./money-text";

describe("MoneyText", () => {
  test('renders "₹1,23,456.78" from the decimal string "123456.78" with tabular figures', () => {
    render(<MoneyText value="123456.78" />);
    const el = screen.getByText("₹1,23,456.78");
    expect(el).toHaveClass("tabular-nums");
  });

  test("abbreviates above a lakh and keeps the exact value as a title", () => {
    render(<MoneyText value="12500000" abbreviate />);
    expect(screen.getByText("₹1.25Cr")).toHaveAttribute("title", "₹1,25,00,000.00");
  });

  test("throws when handed a number instead of a decimal string", () => {
    const badValue = 123.45 as unknown as string;
    expect(() => render(<MoneyText value={badValue} />)).toThrow(TypeError);
  });
});
