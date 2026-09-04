"use client";

import { useState } from "react";
import { PageHeader } from "@/components/primitives/page-header";
import { Tabs } from "@/components/primitives/tabs";
import { useUser } from "@/lib/auth";
import { ApiKeysTab } from "./api-keys-tab";
import { CategoriesTab } from "./categories-tab";
import { ExtractionTab } from "./extraction-tab";
import { ForecastTab } from "./forecast-tab";
import { GstinsTab } from "./gstins-tab";
import { MailTab } from "./mail-tab";
import { MembersTab } from "./members-tab";
import { OrgTab } from "./org-tab";

export type SettingsTab = "org" | "gstins" | "categories" | "members" | "extraction" | "api-keys" | "mail" | "forecast";
export const SETTINGS_TABS: readonly SettingsTab[] = ["org", "gstins", "categories", "members", "extraction", "api-keys", "mail", "forecast"];

const TABS: readonly { value: SettingsTab; label: string; hint?: string }[] = [
  { value: "org", label: "Organisation" },
  { value: "gstins", label: "GSTINs" },
  { value: "categories", label: "Categories" },
  { value: "members", label: "Users & roles" },
  { value: "extraction", label: "Extraction" },
  { value: "api-keys", label: "API keys" },
  { value: "mail", label: "Mail" },
  { value: "forecast", label: "Forecast" },
];

const EDIT_ROLES = new Set(["owner", "accountant"]);

/** §11 /settings. Owner-only tabs (members, extraction, API keys) render read-only for other roles. */
export function SettingsView({ initialTab = "org" }: { initialTab?: SettingsTab }) {
  const [tab, setTab] = useState<SettingsTab>(initialTab);
  const { data: me } = useUser();
  const isOwner = me?.role === "owner";
  const canEdit = EDIT_ROLES.has(me?.role ?? "");

  return (
    <div className="space-y-6">
      <PageHeader title="Settings," emphasis="tuned" description={me?.org ? `${me.org.name} · you are ${me.role}` : undefined} />
      <Tabs items={TABS} value={tab} onChange={setTab} ariaLabel="Settings section" />
      <div role="tabpanel">
        {tab === "org" && <OrgTab canEdit={isOwner} />}
        {tab === "gstins" && <GstinsTab canEdit={canEdit} />}
        {tab === "categories" && <CategoriesTab canEdit={canEdit} />}
        {tab === "members" && <MembersTab isOwner={isOwner} currentEmail={me?.user.email} />}
        {tab === "extraction" && <ExtractionTab isOwner={isOwner} />}
        {tab === "api-keys" && <ApiKeysTab isOwner={isOwner} />}
        {tab === "mail" && <MailTab isOwner={isOwner} canEdit={canEdit} />}
        {tab === "forecast" && <ForecastTab canEdit={canEdit} />}
      </div>
    </div>
  );
}
