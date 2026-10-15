"use client";

import { useState } from "react";
import { ChevronDownIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/crm/api";
import { STAGE_LABELS } from "@/lib/crm/format";
import type { BulkAction, JobOut, PeopleFilter, Stage } from "@/lib/crm/types";
import { STAGES } from "@/lib/crm/types";
import { useJob } from "../use-job";

export function BulkToolbar({
  selected,
  total,
  filter,
  onClear,
  onDone,
}: {
  selected: string[];
  total: number;
  filter: PeopleFilter;
  onClear: () => void;
  onDone: () => void;
}) {
  const { start, running } = useJob();
  const [applyAll, setApplyAll] = useState(false);
  const [tag, setTag] = useState("");
  const count = applyAll ? total : selected.length;

  const run = (action: BulkAction["action"], extra: Partial<BulkAction> = {}) => {
    const body: BulkAction = applyAll
      ? { filter: { ...filter, page: 1 }, action, limit: 5000, ...extra }
      : { ids: selected, action, ...extra };
    void start(() => api.post<JobOut>("/people/bulk", body), {
      pending: `Applying to ${count}…`,
      success: (j) => `Done: ${String(j.result?.created ?? count)} of ${String(j.result?.people ?? count)}`,
      onDone,
    });
  };

  if (!selected.length && !applyAll) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/60 px-3 py-2 text-sm">
      <span className="font-medium tabular-nums">{count} selected</span>
      {total > selected.length && (
        <Button variant="link" size="sm" onClick={() => setApplyAll((v) => !v)}>
          {applyAll ? "selected only" : `apply to all ${total}`}
        </Button>
      )}
      <Button size="sm" variant="outline" disabled={running} onClick={() => run("fetch_tweets")}>
        Refresh tweets
      </Button>
      <Button size="sm" variant="outline" disabled={running} onClick={() => run("analyze")}>
        Analyze
      </Button>
      <Button size="sm" variant="outline" disabled={running} onClick={() => run("refresh_profiles")}>
        Refresh profiles
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button size="sm" variant="outline" disabled={running} />}>
          Stage <ChevronDownIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Move to stage</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {STAGES.map((s) => (
            <DropdownMenuItem key={s} onClick={() => run("set_stage", { stage: s })}>
              {STAGE_LABELS[s as Stage]}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <form
        className="flex items-center gap-1"
        onSubmit={(e) => {
          e.preventDefault();
          if (tag.trim()) run("add_tag", { tag: tag.trim() });
        }}
      >
        <Input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="tag" className="h-7 w-28 text-[0.8rem]" />
        <Button size="sm" variant="outline" type="submit" disabled={running || !tag.trim()}>
          + tag
        </Button>
        <Button size="sm" variant="ghost" type="button" disabled={running || !tag.trim()} onClick={() => run("remove_tag", { tag: tag.trim() })}>
          − tag
        </Button>
      </form>
      <Button
        size="icon-sm"
        variant="ghost"
        className="ml-auto"
        onClick={() => {
          setApplyAll(false);
          onClear();
        }}
        aria-label="Clear selection"
      >
        <XIcon />
      </Button>
    </div>
  );
}
