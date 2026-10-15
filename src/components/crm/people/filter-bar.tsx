"use client";

import { useEffect, useState } from "react";
import { ChevronDownIcon, SearchIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { SimpleSelect } from "../simple-select";
import { countActive, DEFAULT_FILTER } from "@/lib/crm/filters";
import { RELATION_LABELS, SORT_LABELS, STAGE_LABELS } from "@/lib/crm/format";
import type { PeopleFilter, Relation, SortKey, Stage } from "@/lib/crm/types";
import { STAGES } from "@/lib/crm/types";

export function FilterBar({ filter, onChange }: { filter: PeopleFilter; onChange: (f: PeopleFilter) => void }) {
  const [q, setQ] = useState(filter.q ?? "");
  const [prevQ, setPrevQ] = useState(filter.q ?? "");
  if ((filter.q ?? "") !== prevQ) {
    // URL changed from outside (saved view, reset): adopt it.
    setPrevQ(filter.q ?? "");
    setQ(filter.q ?? "");
  }
  useEffect(() => {
    const t = setTimeout(() => {
      if ((filter.q ?? "") !== q) onChange({ ...filter, q: q || null, page: 1 });
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const set = (patch: Partial<PeopleFilter>) => onChange({ ...filter, ...patch, page: 1 });
  const stages = filter.stage ?? [];
  const active = countActive(filter);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative">
        <SearchIcon className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Handle, name, bio" className="h-7 w-56 pl-8 text-[0.8rem]" />
      </div>
      <SimpleSelect
        value={filter.relation ?? "any"}
        onChange={(v) => set({ relation: (v as Relation) ?? "any" })}
        options={Object.entries(RELATION_LABELS).map(([value, label]) => ({ value, label }))}
        className="w-48"
      />
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
          {stages.length ? `Stages: ${stages.length}` : "Stage"} <ChevronDownIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {STAGES.map((s) => (
            <DropdownMenuCheckboxItem
              key={s}
              checked={stages.includes(s)}
              closeOnClick={false}
              onCheckedChange={(checked) => set({ stage: checked ? [...stages, s] : stages.filter((x) => x !== s) })}
            >
              {STAGE_LABELS[s as Stage]}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <SimpleSelect
        value={filter.score_min ? String(filter.score_min) : "0"}
        onChange={(v) => set({ score_min: v && v !== "0" ? Number(v) : null })}
        options={[
          { value: "0", label: "Any score" },
          { value: "3", label: "Score ≥ 3" },
          { value: "4", label: "Score ≥ 4" },
          { value: "5", label: "Score 5" },
        ]}
        className="w-36"
      />
      <Input
        type="number"
        inputMode="numeric"
        placeholder="followers from"
        value={filter.followers_min ?? ""}
        onChange={(e) => set({ followers_min: e.target.value ? Number(e.target.value) : null })}
        className="h-7 w-24 text-[0.8rem]"
      />
      <Input
        type="number"
        inputMode="numeric"
        placeholder="to"
        value={filter.followers_max ?? ""}
        onChange={(e) => set({ followers_max: e.target.value ? Number(e.target.value) : null })}
        className="h-7 w-20 text-[0.8rem]"
      />
      <Label className="flex items-center gap-1.5 text-xs">
        <Checkbox checked={filter.has_analysis === true} onCheckedChange={(c) => set({ has_analysis: c ? true : null })} />
        analyzed
      </Label>
      <Label className="flex items-center gap-1.5 text-xs">
        <Checkbox checked={filter.verified === true} onCheckedChange={(c) => set({ verified: c ? true : null })} />
        verified
      </Label>
      <Label className="flex items-center gap-1.5 text-xs">
        <Checkbox checked={filter.overdue === true} onCheckedChange={(c) => set({ overdue: c ? true : null })} />
        overdue
      </Label>
      <div className="ml-auto flex items-center gap-2">
        <SimpleSelect
          value={filter.sort ?? "-last_event"}
          onChange={(v) => set({ sort: (v as SortKey) ?? "-last_event" })}
          options={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))}
          className="w-48"
        />
        {active > 0 && (
          <Button variant="ghost" size="sm" onClick={() => onChange({ ...DEFAULT_FILTER, sort: filter.sort })}>
            <XIcon /> Reset ({active})
          </Button>
        )}
      </div>
    </div>
  );
}
