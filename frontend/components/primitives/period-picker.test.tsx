import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { PeriodPicker } from "./period-picker";

describe("PeriodPicker", () => {
  test("selecting Last FY from a date in Jan 2027 emits FY 2025-26; FY to date emits 2026-04-01 onwards", () => {
    // Arrange
    const onChange = vi.fn();
    render(<PeriodPicker onChange={onChange} today="2027-01-15" />);
    const select = screen.getByLabelText("Period");

    // Act
    fireEvent.change(select, { target: { value: "fy_to_date" } });
    fireEvent.change(select, { target: { value: "last_fy" } });

    // Assert
    expect(onChange).toHaveBeenNthCalledWith(1, {
      from: "2026-04-01",
      to: "2027-01-15",
      fy: "2026-27",
      label: "FY2026-27 to date",
    });
    expect(onChange).toHaveBeenNthCalledWith(2, {
      from: "2025-04-01",
      to: "2026-03-31",
      fy: "2025-26",
      label: "FY2025-26",
    });
  });

  test("custom range shows date inputs and emits the chosen bounds", () => {
    const onChange = vi.fn();
    render(<PeriodPicker onChange={onChange} today="2027-01-15" />);
    fireEvent.change(screen.getByLabelText("Period"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-04-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2027-03-31" } });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ from: "2026-04-01", to: "2027-03-31", fy: "2026-27" }),
    );
  });

  test("inverted custom range surfaces an error instead of emitting", () => {
    const onChange = vi.fn();
    render(<PeriodPicker onChange={onChange} today="2027-01-15" />);
    fireEvent.change(screen.getByLabelText("Period"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2027-02-01" } });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(onChange).toHaveBeenCalledTimes(1); // only the initial "custom" emit (from == to == today)
  });
});
