"use client";

import { X } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Input } from "@/components/ui/input";
import { ICON_STROKE } from "@/lib/constants";
import { partyDisplayName, useParty, usePartySearch } from "@/lib/parties";
import type { Party, PartyKind } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface PartyComboboxProps {
  value: string;
  onChange: (partyId: string, party: Party | null) => void;
  kind?: PartyKind | "";
  placeholder?: string;
  id?: string;
  className?: string;
  /** Exclude one party (e.g. the merge source) from the suggestions. */
  excludeId?: string;
}

const DEBOUNCE_MS = 200;

/** Search-as-you-type party picker backed by GET /api/parties/?q=. Stores the party id. */
export function PartyCombobox({ value, onChange, kind = "", placeholder = "Search parties…", id, className, excludeId }: PartyComboboxProps) {
  const listId = useId();
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const selected = useParty(value, value !== "");
  const results = usePartySearch(query);

  useEffect(() => {
    const handle = setTimeout(() => setQuery(text.trim()), DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [text]);

  const options = (results.data ?? []).filter((party) => party.id !== excludeId && (kind === "" || party.kind === kind || party.kind === "both"));

  if (value !== "") {
    return (
      <div className={cn("flex h-9 items-center justify-between gap-2 rounded-full border border-input bg-surface px-3 text-sm", className)}>
        <span className="truncate">{selected.data ? partyDisplayName(selected.data) : "…"}</span>
        <button type="button" aria-label="Clear party" className="text-muted hover:text-foreground" onClick={() => onChange("", null)}>
          <X size={14} strokeWidth={ICON_STROKE} aria-hidden />
        </button>
      </div>
    );
  }

  return (
    <div className={cn("relative", className)}>
      <Input
        id={id}
        role="combobox"
        aria-expanded={isOpen && options.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        placeholder={placeholder}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 150)}
      />
      {isOpen && options.length > 0 && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-card border border-border bg-popover p-1 text-sm">
          {options.map((party) => (
            <li key={party.id} role="option" aria-selected={false}>
              <button
                type="button"
                className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left hover:bg-secondary"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(party.id, party);
                  setText("");
                  setIsOpen(false);
                }}
              >
                <span className="truncate">{partyDisplayName(party)}</span>
                <span className="ml-2 text-xs text-muted">{party.kind}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
