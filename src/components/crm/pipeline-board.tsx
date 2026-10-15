"use client";

import Link from "next/link";
import useSWR from "swr";
import { MoreHorizontalIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { api, fetcher } from "@/lib/crm/api";
import { daysSince, daysUntil, STAGE_LABELS } from "@/lib/crm/format";
import type { PersonOut, PipelineOut, Stage } from "@/lib/crm/types";
import { STAGES } from "@/lib/crm/types";
import { BackendAlert } from "./backend-alert";
import { PersonAvatar } from "./person-avatar";
import { ScoreDots, StageBadge } from "./badges";
import { cn } from "cn";

const ALWAYS: Stage[] = ["followed", "engaged", "followed_back", "no_response"];
const ORDER: Stage[] = ["followed", "engaged", "followed_back", "no_response", "candidate", "unfollowed", "lost", "ignored"];

function PersonCard({ p, onMove }: { p: PersonOut; onMove: (id: string, stage: Stage) => void }) {
  const waited = daysSince(p.last_event_at && p.stage === "followed" ? null : null);
  void waited;
  const left = daysUntil(p.deadline_at);
  return (
    <div className={cn("space-y-2 rounded-lg bg-card p-3 text-sm ring-1 ring-foreground/10", p.overdue && "ring-red-500/40")}>
      <div className="flex items-start gap-2">
        <PersonAvatar src={p.avatar_url} name={p.name} handle={p.handle} className="size-7" />
        <div className="min-w-0 flex-1">
          <Link href={`/crm/people/${p.id}`} className="block truncate font-medium hover:underline">
            @{p.handle ?? p.id}
          </Link>
          {p.name && <div className="truncate text-xs text-muted-foreground">{p.name}</div>}
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button size="icon-xs" variant="ghost" aria-label="Действия" />}>
            <MoreHorizontalIcon />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Перевести</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {STAGES.filter((s) => s !== p.stage).map((s) => (
              <DropdownMenuItem key={s} onClick={() => onMove(p.id, s)}>
                {STAGE_LABELS[s]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground tabular-nums">
        {p.relevance_score !== null && <ScoreDots score={p.relevance_score} />}
        {p.is_follower && <span className="text-emerald-700 dark:text-emerald-300">фолловит</span>}
        {p.deadline_at && (p.stage === "followed" || p.stage === "engaged") && left !== null && (
          <span className={cn(left < 0 && "font-medium text-red-600 dark:text-red-400")}>
            {left < 0 ? `просрочен на ${-left} дн.` : left === 0 ? "дедлайн сегодня" : `ещё ${left} дн.`}
          </span>
        )}
      </div>
    </div>
  );
}

export function PipelineBoard() {
  const { data, error, isLoading, mutate } = useSWR<PipelineOut>("/pipeline", fetcher);

  const move = async (id: string, stage: Stage) => {
    try {
      await api.patch(`/people/${id}/contact`, { stage });
      toast.success(`→ ${STAGE_LABELS[stage]}`);
      void mutate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Ошибка");
    }
  };

  if (error) return <BackendAlert error={error} />;
  if (isLoading || !data) return <Skeleton className="h-96 rounded-xl" />;

  const visible = ORDER.filter((s) => ALWAYS.includes(s) || (data.counts[s] ?? 0) > 0);

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold tracking-tight">Пайплайн</h1>
      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2">
        {visible.map((s) => {
          const items = data.columns[s] ?? [];
          return (
            <div key={s} className="w-72 shrink-0 space-y-2">
              <div className="flex items-center justify-between px-1">
                <StageBadge stage={s} />
                <span className="text-xs text-muted-foreground tabular-nums">{items.length}</span>
              </div>
              <div className="space-y-2 rounded-xl bg-muted/40 p-2">
                {items.length === 0 && <p className="px-1 py-6 text-center text-xs text-muted-foreground">пусто</p>}
                {items.map((p) => (
                  <PersonCard key={p.id} p={p} onMove={(id, st) => void move(id, st)} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
