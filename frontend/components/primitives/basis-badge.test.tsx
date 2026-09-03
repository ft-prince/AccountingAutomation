import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { BasisBadge } from "./basis-badge";

describe("BasisBadge", () => {
  test('renders "Accrual · 12 pending"', () => {
    render(<BasisBadge basis="accrual" pendingCount={12} />);
    expect(screen.getByText("Accrual · 12 pending")).toBeInTheDocument();
  });

  test('renders "Cash · 0 pending"', () => {
    render(<BasisBadge basis="cash" pendingCount={0} />);
    expect(screen.getByText("Cash · 0 pending")).toBeInTheDocument();
  });
});
