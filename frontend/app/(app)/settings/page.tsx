import type { Metadata } from "next";
import { SETTINGS_TABS, SettingsView, type SettingsTab } from "@/components/settings/settings-view";

export const metadata: Metadata = { title: "Settings · Nexren Finance" };

function tabFrom(value: string | string[] | undefined): SettingsTab {
  const candidate = Array.isArray(value) ? value[0] : value;
  return SETTINGS_TABS.find((tab) => tab === candidate) ?? "org";
}

/** `/settings?tab=mail` deep-links straight to a tab (the inbox empty state uses it). */
export default async function SettingsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  return <SettingsView initialTab={tabFrom(params.tab)} />;
}
