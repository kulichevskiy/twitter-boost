"use client";

import Link from "next/link";
import { ArrowDownIcon, ArrowUpIcon, BadgeCheckIcon, ChevronsUpDownIcon } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { compact, relativeTime } from "@/lib/crm/format";
import type { PersonOut, SortKey } from "@/lib/crm/types";
import { cn } from "cn";
import { PersonAvatar } from "../person-avatar";
import { RelationBadges, ScoreDots, StageBadge } from "../badges";

type SortField = "handle" | "followers" | "score" | "last_event";

/** Which direction a column opens with on first click. */
const DEFAULT_DESC: Record<SortField, boolean> = { handle: false, followers: true, score: true, last_event: true };

function parseSort(sort: SortKey | undefined): { field: string; desc: boolean } {
  const s = sort ?? "-last_event";
  return s.startsWith("-") ? { field: s.slice(1), desc: true } : { field: s, desc: false };
}

function SortableHead({
  field,
  label,
  sort,
  onSort,
  className,
}: {
  field: SortField;
  label: string;
  sort: SortKey | undefined;
  onSort?: (sort: SortKey) => void;
  className?: string;
}) {
  const current = parseSort(sort);
  const active = current.field === field;
  const next: SortKey = active ? ((current.desc ? field : `-${field}`) as SortKey) : ((DEFAULT_DESC[field] ? `-${field}` : field) as SortKey);
  const Icon = active ? (current.desc ? ArrowDownIcon : ArrowUpIcon) : ChevronsUpDownIcon;
  return (
    <TableHead className={className} aria-sort={active ? (current.desc ? "descending" : "ascending") : "none"}>
      <button
        type="button"
        onClick={() => onSort?.(next)}
        className={cn(
          "-mx-1 inline-flex items-center gap-1 rounded px-1 py-0.5 hover:text-foreground",
          active ? "text-foreground" : "text-muted-foreground",
          className?.includes("text-right") && "flex-row-reverse",
        )}
      >
        {label}
        <Icon className={cn("size-3.5", !active && "opacity-50")} />
      </button>
    </TableHead>
  );
}

export function PeopleTable({
  people,
  selected,
  onToggle,
  onToggleAll,
  sort,
  onSort,
}: {
  people: PersonOut[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (checked: boolean) => void;
  sort?: SortKey;
  onSort?: (sort: SortKey) => void;
}) {
  const allChecked = people.length > 0 && people.every((p) => selected.has(p.id));
  const some = !allChecked && people.some((p) => selected.has(p.id));
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-foreground/10">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">
              <Checkbox checked={allChecked} indeterminate={some} onCheckedChange={(c) => onToggleAll(!!c)} aria-label="Select all" />
            </TableHead>
            <SortableHead field="handle" label="Person" sort={sort} onSort={onSort} />
            <SortableHead field="followers" label="Followers" sort={sort} onSort={onSort} className="text-right" />
            <TableHead>Relation</TableHead>
            <TableHead>Stage</TableHead>
            <SortableHead field="score" label="Score" sort={sort} onSort={onSort} />
            <TableHead>Tags</TableHead>
            <SortableHead field="last_event" label="Last event" sort={sort} onSort={onSort} className="text-right" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {people.map((p) => (
            <TableRow key={p.id} data-state={selected.has(p.id) ? "selected" : undefined}>
              <TableCell>
                <Checkbox checked={selected.has(p.id)} onCheckedChange={() => onToggle(p.id)} aria-label="Select" />
              </TableCell>
              <TableCell className="max-w-md">
                <Link href={`/crm/people/${p.id}`} className="flex items-start gap-3">
                  <PersonAvatar src={p.avatar_url} name={p.name} handle={p.handle} className="mt-0.5" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1 font-medium">
                      <span className="truncate">@{p.handle ?? p.id}</span>
                      {p.verified && <BadgeCheckIcon className="size-3.5 shrink-0 text-blue-500" />}
                      {p.name && <span className="truncate font-normal text-muted-foreground">· {p.name}</span>}
                    </div>
                    {p.bio && <div className="line-clamp-2 text-xs text-muted-foreground">{p.bio}</div>}
                  </div>
                </Link>
              </TableCell>
              <TableCell className="text-right tabular-nums">{compact(p.followers_count)}</TableCell>
              <TableCell>
                <RelationBadges isFollower={p.is_follower} isFollowing={p.is_following} />
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <StageBadge stage={p.stage} />
                  {p.overdue && <Badge variant="destructive">overdue</Badge>}
                </div>
              </TableCell>
              <TableCell>
                <ScoreDots score={p.relevance_score} />
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {p.tags.map((t) => (
                    <Badge key={t.id} variant="outline">
                      {t.name}
                    </Badge>
                  ))}
                </div>
              </TableCell>
              <TableCell className="text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
                {relativeTime(p.last_event_at ?? p.first_seen_at)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
