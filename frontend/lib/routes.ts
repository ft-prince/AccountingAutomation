// PROJECT_SPECS §11 — frontend routes. Shared by the sidebar, middleware and placeholder pages.
export const ROUTES = { login: "/login", dashboard: "/dashboard" } as const;

export interface NavRoute {
  href: string;
  label: string;
}

export const APP_NAV: readonly NavRoute[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/review", label: "Review" },
  { href: "/invoices", label: "Invoices" },
  { href: "/payments", label: "Payments" },
  { href: "/bank", label: "Bank" },
  { href: "/parties", label: "Parties" },
  { href: "/inbox", label: "Inbox" },
  { href: "/reports", label: "Reports" },
  { href: "/forecast", label: "Forecast" },
  { href: "/reconciliation", label: "Reconciliation" },
  { href: "/settings", label: "Settings" },
  { href: "/guide", label: "Guide" },
];

export const DEFAULT_BRAND_NAME = "Nexren Finance";
