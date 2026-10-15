"use client";

import Link from "next/link";
import { BadgeCheckIcon } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { compact, relativeTime } from "@/lib/crm/format";
import type { PersonOut } from "@/lib/crm/types";
import { PersonAvatar } from "../person-avatar";
import { RelationBadges, ScoreDots, StageBadge } from "../badges";

export function PeopleTable({
  people,
  selected,
  onToggle,
  onToggleAll,
}: {
  people: PersonOut[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (checked: boolean) => void;
}) {
  const allChecked = people.length > 0 && people.every((p) => selected.has(p.id));
  const some = !allChecked && people.some((p) => selected.has(p.id));
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-foreground/10">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">
              <Checkbox checked={allChecked} indeterminate={some} onCheckedChange={(c) => onToggleAll(!!c)} aria-label="Выбрать всех" />
            </TableHead>
            <TableHead>Человек</TableHead>
            <TableHead className="text-right">Фолл.</TableHead>
            <TableHead>Связь</TableHead>
            <TableHead>Стадия</TableHead>
            <TableHead>Оценка</TableHead>
            <TableHead>Теги</TableHead>
            <TableHead className="text-right">Событие</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {people.map((p) => (
            <TableRow key={p.id} data-state={selected.has(p.id) ? "selected" : undefined}>
              <TableCell>
                <Checkbox checked={selected.has(p.id)} onCheckedChange={() => onToggle(p.id)} aria-label="Выбрать" />
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
                  {p.overdue && <Badge variant="destructive">просрочен</Badge>}
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
