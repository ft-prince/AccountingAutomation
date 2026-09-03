import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { StatTile } from "./stat-tile";

describe("StatTile delta chip", () => {
  test("up direction uses the success colour only", () => {
    render(<StatTile label="Receivables" value="₹4,20,000.00" delta={{ value: "+12%", direction: "up" }} />);
    const chip = screen.getByText("+12%");
    expect(chip).toHaveClass("text-success");
    expect(chip).not.toHaveClass("text-danger");
    expect(chip).toHaveAttribute("data-direction", "up");
  });

  test("down direction uses the danger colour only", () => {
    render(<StatTile label="Payables" value="₹1,10,000.00" delta={{ value: "-3%", direction: "down" }} />);
    const chip = screen.getByText("-3%");
    expect(chip).toHaveClass("text-danger");
    expect(chip).not.toHaveClass("text-success");
  });

  test("flat direction stays muted and shows the hint", () => {
    render(<StatTile label="Runway" value="9.2 months" delta={{ value: "0%", direction: "flat" }} hint="vs last month" />);
    expect(screen.getByText("0%")).toHaveClass("text-muted");
    expect(screen.getByText("vs last month")).toBeInTheDocument();
  });

  test("headline number is serif-italic display type", () => {
    render(<StatTile label="Cash" value="₹9,99,999.00" />);
    expect(screen.getByText("₹9,99,999.00")).toHaveClass("font-display", "italic");
  });
});
