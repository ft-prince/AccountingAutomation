import { describe, expect, test } from "vitest";
import { buildInvoicesQuery, countActiveFilters, EMPTY_INVOICE_FILTERS, invoicesExportUrl, nextOrdering } from "./invoice-filters";

describe("buildInvoicesQuery", () => {
  test("serialises every §10 filter and omits empty ones", () => {
    const query = buildInvoicesQuery(
      {
        ...EMPTY_INVOICE_FILTERS,
        status: "confirmed",
        direction: "outward",
        party: "p1",
        fy: "2026-27",
        period: "2026-08",
        payment_status: "overdue",
        category: "c1",
        from: "2026-04-01",
        to: "2026-08-31",
        min: "1000",
        max: "50000.50",
        q: "NX/26",
        ordering: "-total",
      },
      { cursor: "abc", pageSize: 50 },
    );
    expect(query).toBe(
      "?status=confirmed&direction=outward&party=p1&fy=2026-27&period=2026-08&payment_status=overdue&category=c1&from=2026-04-01&to=2026-08-31&min=1000&max=50000.50&q=NX%2F26&ordering=-total&page_size=50&cursor=abc",
    );
  });

  test("defaults carry only ordering and page size", () => {
    expect(buildInvoicesQuery(EMPTY_INVOICE_FILTERS)).toBe("?ordering=-invoice_date&page_size=25");
    expect(countActiveFilters(EMPTY_INVOICE_FILTERS)).toBe(0);
  });

  test("export url mirrors the filters with type=raw and no paging", () => {
    expect(invoicesExportUrl({ ...EMPTY_INVOICE_FILTERS, status: "needs_review", q: "a b" })).toBe("/api/exports/csv?type=raw&status=needs_review&q=a+b");
  });

  test("sort toggles desc → asc → desc", () => {
    expect(nextOrdering("-invoice_date", "total")).toBe("-total");
    expect(nextOrdering("-total", "total")).toBe("total");
    expect(nextOrdering("total", "total")).toBe("-total");
  });
});

describe("URL round trip", () => {
  test("filters survive a trip through the page URL and defaults are omitted", async () => {
    const { filtersFromSearchParams, filtersToSearchParams } = await import("./invoice-filters");
    const filters = { ...EMPTY_INVOICE_FILTERS, status: "needs_review" as const, q: "tata", ordering: "-total" as const };
    const url = filtersToSearchParams(filters);
    expect(url).toBe("?status=needs_review&q=tata&ordering=-total");
    expect(filtersFromSearchParams(new URLSearchParams(url))).toEqual(filters);
    expect(filtersToSearchParams(EMPTY_INVOICE_FILTERS)).toBe("");
  });
});
