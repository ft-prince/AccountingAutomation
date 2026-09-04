import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { renderWithClient } from "@/lib/test-utils";
import type { ForecastRun } from "@/lib/types";
import { ForecastView } from "./forecast-view";

// Recharts needs layout; the band chart's data shaping is unit-tested in lib/forecast-data. Here the
// mock records which series the view asked for.
const bandProps = vi.hoisted(() => vi.fn());
vi.mock("@/components/charts", () => ({
  ChartFrame: ({ title, children, actions }: { title: string; children: React.ReactNode; actions?: React.ReactNode }) => (
    <section aria-label={title}>{actions}{children}</section>
  ),
  ForecastBand: (props: unknown) => { bandProps(props); return <div data-testid="forecast-band" />; },
}));
vi.mock("@/components/parties/party-combobox", () => ({ PartyCombobox: () => <input aria-label="party" /> }));

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), api: apiMock }));

const points = [{ date: "2026-09-05", p10: "100", p50: "150", p90: "200", deterministic: "160" }];
const baseRun: ForecastRun = { id: "run1", as_of: "2026-09-04", horizon_days: 91, seed: 7, params: {}, inputs_hash: "h", history_days: 120, insufficient_history: false, opening_cash: "500000.00", backtest_mape: "0.12", backtest_coverage: "0.82", backtest_n_origins: 5, runway_date: null, narrative: null, status: "done", error: "", created_at: "", points };

function routes(run: ForecastRun): (path: string) => Promise<unknown> {
  return async (path: string) => {
    if (path === "/api/forecast/latest") return run;
    if (path === "/api/auth/me") return { user: { id: "u", email: "e", full_name: "n" }, org: null, role: "owner", orgs: [] };
    if (path === "/api/forecast/drivers") return [];
    if (path === "/api/forecast/risk/customers") return [];
    if (path === "/api/forecast/anomalies") return { as_of: "2026-09-04", window_days: 90, expenses: [], duplicates: [], concentration: { top1_party: null, top1_party_name: "", top1_share: "0", top3_parties: [], top3_share: "0", is_top1_flagged: false, is_top3_flagged: false } };
    if (path === "/api/forecast/scenarios/") return { results: [{ id: "s1", name: "Tata late", overrides: [{ kind: "delay_customer", party: "p1", days: 30 }], created_at: "", updated_at: "" }], next: null, previous: null };
    if (path === "/api/forecast/scenarios/s1/run") return { scenario: "s1", base_run: "run1", as_of: "2026-09-04", horizon_days: 91, n_paths: 100, seed: 7, runway_date: "2026-11-01", points: [{ date: "2026-09-05", p10: "1", p50: "120", p90: "3", deterministic: "0" }] };
    if (path === "/api/forecast/recurring/") return { results: [], next: null, previous: null };
    throw new Error(`unmocked ${path}`);
  };
}

afterEach(() => { apiMock.mockReset(); bandProps.mockReset(); });

describe("ForecastView", () => {
  test("insufficient history shows the deterministic line only and explains the 90-day rule", async () => {
    apiMock.mockImplementation(routes({ ...baseRun, history_days: 40, insufficient_history: true, backtest_coverage: null }));
    renderWithClient(<ForecastView today="2026-09-04" />);
    await waitFor(() => expect(screen.getByTestId("forecast-band")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Insufficient history — deterministic view only");
    expect(screen.getByRole("status")).toHaveTextContent("at least 90 days");
    expect(bandProps).toHaveBeenLastCalledWith(expect.objectContaining({ showBands: false }));
    expect(screen.queryByText(/Bands calibrated|Bands miscalibrated/)).not.toBeInTheDocument();
  });

  test("calibrated run shows the success badge and bands; running a scenario adds the overlay series", async () => {
    apiMock.mockImplementation(routes(baseRun));
    renderWithClient(<ForecastView today="2026-09-04" />);
    await waitFor(() => expect(screen.getByText("Bands calibrated · 82% coverage · 5 origins")).toBeInTheDocument());
    expect(bandProps).toHaveBeenLastCalledWith(expect.objectContaining({ showBands: true, overlay: [] }));
    expect(screen.getByText("> horizon")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /run$/i }));
    await waitFor(() => expect(screen.getByText("Scenario runway")).toBeInTheDocument());
    expect(bandProps).toHaveBeenLastCalledWith(expect.objectContaining({ overlay: [expect.objectContaining({ date: "2026-09-05", p50: "120" })] }));
    expect(screen.getByText("1 Nov 2026")).toBeInTheDocument();
  });

  test("miscalibrated coverage renders the warning badge", async () => {
    apiMock.mockImplementation(routes({ ...baseRun, backtest_coverage: "0.00" }));
    renderWithClient(<ForecastView today="2026-09-04" />);
    await waitFor(() => expect(screen.getByText("Bands miscalibrated · 0% coverage · 5 origins")).toBeInTheDocument());
  });
});
