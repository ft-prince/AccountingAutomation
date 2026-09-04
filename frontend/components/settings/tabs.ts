/** Plain module (no "use client"): the server page imports these, and Next replaces
 * non-component exports of client modules with proxies that are not real values. */
export type SettingsTab =
  | "org"
  | "gstins"
  | "categories"
  | "members"
  | "extraction"
  | "api-keys"
  | "mail"
  | "forecast";

export const SETTINGS_TABS: readonly SettingsTab[] = [
  "org",
  "gstins",
  "categories",
  "members",
  "extraction",
  "api-keys",
  "mail",
  "forecast",
];
