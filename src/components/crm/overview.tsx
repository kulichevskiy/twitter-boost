"use client";

import Link from "next/link";
import useSWR from "swr";
import { RefreshCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, fetcher } from "@/lib/crm/api";
import { eventLabel, formatDate, relativeTime, STAGE_LABELS } from "@/lib/crm/format";
import type { JobOut, OverviewOut, Stage } from "@/lib/crm/types";
import { BackendAlert } from "./backend-alert";
import { EventFeed } from "./event-feed";
import { PersonAvatar } from "./person-avatar";
import { StageBadge } from "./badges";
import { useJob } from "./use-job";

function Stat({ label, value, href, tone }: { label: string; value: number; href?: string; tone?: "warn" | "danger" }) {
  const body = (
    <Card size="sm" className="h-full">
      <CardContent>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`text-2xl font-semibold tabular-nums ${tone === "danger" && value > 0 ? "text-red-600 dark:text-red-400" : tone === "warn" && value > 0 ? "text-amber-600 dark:text-amber-400" : ""}`}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
  return href ? (
    <Link href={href} className="block rounded-xl transition-transform hover:-translate-y-px">
      {body}
    </Link>
  ) : (
    body
  );
}

export function Overview() {
  const { data, error, isLoading, mutate } = useSWR<OverviewOut>("/overview", fetcher, {
    refreshInterval: (d) => (d && (d.jobs.running > 0 || d.jobs.queued > 0) ? 3000 : 30000),
  });
  const { start, running } = useJob();

  if (error) return <BackendAlert error={error} />;
  if (isLoading || !data) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
    );
  }

  const sync = data.last_sync;
  const busy = data.jobs.running > 0 || data.jobs.queued > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {data.account && (
            <>
              <PersonAvatar src={data.account.avatar_url} name={data.account.name} handle={data.account.handle} className="size-10" />
              <div>
                <div className="font-semibold">{data.account.name ?? "Мой аккаунт"}</div>
                <div className="text-sm text-muted-foreground">
                  @{data.account.handle ?? "?"} · {data.account.followers_count ?? "—"} фолловеров · {data.account.following_count ?? "—"} подписок
                </div>
              </div>
            </>
          )}
          {!data.account && (
            <div className="text-sm text-muted-foreground">
              Аккаунт ещё не синхронизирован. Заполни <Link href="/crm/settings" className="underline">настройки</Link> и запусти синк.
            </div>
          )}
        </div>
        <Button
          size="sm"
          disabled={running || busy}
          onClick={() =>
            start(() => api.post<JobOut>("/syncs/run"), {
              pending: "Синхронизирую списки…",
              success: (j) => {
                const r = j.result ?? {};
                return `Синк ${String(r.status)}: +${String(r.added_followers ?? 0)}/−${String(r.removed_followers ?? 0)} фолловеров, +${String(r.added_following ?? 0)}/−${String(r.removed_following ?? 0)} подписок`;
              },
              onDone: () => void mutate(),
            })
          }
        >
          <RefreshCwIcon className={running || busy ? "animate-spin" : ""} /> Синхронизировать
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Фолловеры" value={data.followers} href="/crm/people?relation=follower" />
        <Stat label="Подписки" value={data.following} href="/crm/people?relation=following" />
        <Stat label="Взаимные" value={data.mutual} href="/crm/people?relation=mutual" />
        <Stat label="Не фоловят в ответ" value={data.not_following_back} href="/crm/people?relation=following_only" />
        <Stat label="Фанаты (я не фоловлю)" value={data.fans} href="/crm/people?relation=follower_only" />
        <Stat label="Ждут ответа" value={data.waiting} href="/crm/pipeline" tone="warn" />
        <Stat label="Просрочено" value={data.overdue} href="/crm/people?overdue=true" tone="danger" />
        <Card size="sm">
          <CardContent>
            <div className="text-xs text-muted-foreground">Очередь</div>
            <div className="text-sm">
              <span className="font-semibold tabular-nums">{data.jobs.queued}</span> в очереди ·{" "}
              <span className="font-semibold tabular-nums">{data.jobs.running}</span> в работе
              {data.jobs.failed > 0 && (
                <>
                  {" "}
                  · <Link href="/crm/syncs" className="text-red-600 underline dark:text-red-400">{data.jobs.failed} ошибок</Link>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Последний синк</CardTitle>
            <CardDescription>
              {sync ? (
                <>
                  {relativeTime(sync.started_at)} · следующий {data.next_sync_at ? formatDate(data.next_sync_at, true) : "выключен"}
                </>
              ) : (
                "Ещё не было"
              )}
            </CardDescription>
          </CardHeader>
          {sync && (
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge variant={sync.status === "ok" ? "secondary" : sync.status === "running" ? "outline" : "destructive"}>{sync.status}</Badge>
                <span className="text-muted-foreground">{sync.kind} · {sync.source} · {sync.requests} запросов</span>
              </div>
              <div className="grid grid-cols-2 gap-1 tabular-nums">
                <span>Фолловеры: {sync.followers_total ?? "—"}</span>
                <span className="text-muted-foreground">+{sync.added_followers} / −{sync.removed_followers}</span>
                <span>Подписки: {sync.following_total ?? "—"}</span>
                <span className="text-muted-foreground">+{sync.added_following} / −{sync.removed_following}</span>
              </div>
              {sync.error && <p className="text-xs text-red-600 dark:text-red-400">{sync.error}</p>}
            </CardContent>
          )}
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Динамика</CardTitle>
            <CardDescription>События за 7 и 30 дней</CardDescription>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm tabular-nums">
              <thead className="text-xs text-muted-foreground">
                <tr>
                  <th className="text-left font-normal">событие</th>
                  <th className="text-right font-normal">7д</th>
                  <th className="text-right font-normal">30д</th>
                </tr>
              </thead>
              <tbody>
                {["followed_me", "unfollowed_me", "i_followed", "i_unfollowed", "profile_changed", "analyzed"].map((t) => (
                  <tr key={t}>
                    <td className="py-0.5">{eventLabel(t)}</td>
                    <td className="text-right">{data.deltas["7d"]?.[t] ?? 0}</td>
                    <td className="text-right">{data.deltas["30d"]?.[t] ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Пайплайн</CardTitle>
            <CardDescription>Контакты по стадиям</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {Object.keys(STAGE_LABELS).map((s) => {
              const n = data.stages[s] ?? 0;
              if (!n) return null;
              return (
                <Link key={s} href={`/crm/people?stage=${s}`} className="flex items-center gap-1.5">
                  <StageBadge stage={s as Stage} />
                  <span className="text-sm tabular-nums">{n}</span>
                </Link>
              );
            })}
            {Object.values(data.stages).every((n) => !n) && <p className="text-sm text-muted-foreground">Пусто. Добавь людей на странице «Люди».</p>}
          </CardContent>
        </Card>
      </div>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Последние события</CardTitle>
        </CardHeader>
        <CardContent>
          <EventFeed events={data.recent_events} />
          <div className="pt-2 text-right">
            <Link href="/crm/events" className="text-sm text-muted-foreground hover:underline">
              Все события →
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
