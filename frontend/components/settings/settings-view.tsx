"use client";

import { useState } from "react";
import { PageHeader } from "@/components/primitives/page-header";
import { PlaceholderCard } from "@/components/primitives/placeholder-card";
import { Tabs } from "@/components/primitives/tabs";
import { useUser } from "@/lib/auth";
import { ApiKeysTab } from "./api-keys-tab";
import { CategoriesTab } from "./categories-tab";
import { ExtractionTab } from "./extraction-tab";
import { GstinsTab } from "./gstins-tab";
import { MembersTab } from "./members-tab";
import { OrgTab } from "./org-tab";

export type SettingsTab = "org" | "gstins" | "categories" | "members" | "extraction" | "api-keys" | "mail" | "forecast";

const TABS: readonly { value: SettingsTab; label: string; hint?: string }[] = [
  { value: "org", label: "Organisation" },
  { value: "gstins", label: "GSTINs" },
  { value: "categories", label: "Categories" },
  { value: "members", label: "Users & roles" },
  { value: "extraction", label: "Extraction" },
  { value: "api-keys", label: "API keys" },
  { value: "mail", label: "Mail", hint: "Phase 16" },
  { value: "forecast", label: "Forecast", hint: "Phase 18" },
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
        {tab === "mail" && <PlaceholderCard title="Mailboxes, style guide and templates" phase={16} description="Connect Gmail / Microsoft, set the writing style and reply templates." className="min-h-[200px]" />}
        {tab === "forecast" && <PlaceholderCard title="Forecast fixed lines" phase={18} description="Rent, salaries, loan EMIs and other fixed outflows for the cashflow engine." className="min-h-[200px]" />}
      </div>
    </div>
  );
}
