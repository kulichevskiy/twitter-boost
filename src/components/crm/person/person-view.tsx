"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ChevronDownIcon, ChevronLeftIcon, RefreshCwIcon, SparklesIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, fetcher } from "@/lib/crm/api";
import type { EventOut, JobOut, PersonDetail } from "@/lib/crm/types";
import { BackendAlert } from "../backend-alert";
import { EventFeed } from "../event-feed";
import { useJob } from "../use-job";
import { AnalysisCard } from "./analysis-card";
import { ContactCard } from "./contact-card";
import { Notes } from "./notes";
import { PersonHeader } from "./person-header";
import { TweetsList } from "./tweets-list";

export function PersonView({ id }: { id: string }) {
  const { data, error, isLoading, mutate } = useSWR<PersonDetail>(`/people/${id}`, fetcher);
  const { start, running } = useJob();
  const [tab, setTab] = useState("analysis");
  const refresh = () => void mutate();

  if (error) return <BackendAlert error={error} />;
  if (isLoading || !data) return <Skeleton className="h-96 rounded-xl" />;

  const { person } = data;
  const timeline: EventOut[] = [
    ...data.events,
    ...data.notes.map<EventOut>((n) => ({
      id: -n.id,
      person_id: id,
      type: "note_added",
      at: n.created_at,
      sync_id: null,
      payload: { preview: n.text.slice(0, 140) },
    })),
  ]
    .filter((e, i, arr) => !(e.type === "note_added" && e.id > 0 && arr.some((x) => x.id < 0 && x.at === e.at)))
    .sort((a, b) => (a.at < b.at ? 1 : -1));

  const analyze = (opts: { force?: boolean; refresh?: boolean }) =>
    start(
      () =>
        api.post<JobOut>(`/people/${id}/analyze?force=${opts.force ? "true" : "false"}&refresh=${opts.refresh ? "true" : "false"}`),
      {
        pending: "Разбираю…",
        success: (j) => (j.result?.created === false ? "Разбор не изменился (кэш)" : `Разобран, оценка ${String(j.result?.score ?? "?")}`),
        onDone: () => {
          refresh();
          setTab("analysis");
        },
      },
    );

  return (
    <div className="space-y-4">
      <Link href="/crm/people" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeftIcon className="size-4" /> Все люди
      </Link>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1 space-y-4">
          <PersonHeader person={person} onChanged={refresh} />
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={running}
              onClick={() =>
                start(() => api.post<JobOut>(`/people/${id}/tweets/refresh`), {
                  pending: "Загружаю твиты…",
                  success: (j) => `Новых твитов: ${String(j.result?.new_tweets ?? 0)}`,
                  onDone: () => {
                    refresh();
                    setTab("tweets");
                  },
                })
              }
            >
              <RefreshCwIcon className={running ? "animate-spin" : ""} /> Обновить твиты
            </Button>
            <div className="flex">
              <Button size="sm" disabled={running} className="rounded-r-none" onClick={() => void analyze({})}>
                <SparklesIcon /> Разобрать
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button size="icon-sm" disabled={running} className="rounded-l-none border-l border-l-background/30" />}>
                  <ChevronDownIcon />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => void analyze({ refresh: true })}>Обновить твиты и разобрать</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => void analyze({ force: true })}>Разобрать заново (без кэша)</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
          <Card size="sm">
            <CardContent>
              <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
                <TabsList variant="line">
                  <TabsTrigger value="analysis">Анализ</TabsTrigger>
                  <TabsTrigger value="tweets">Твиты {data.tweets.length ? `(${data.tweets.length})` : ""}</TabsTrigger>
                  <TabsTrigger value="timeline">Таймлайн</TabsTrigger>
                  <TabsTrigger value="notes">Заметки {data.notes.length ? `(${data.notes.length})` : ""}</TabsTrigger>
                </TabsList>
                <TabsContent value="analysis" className="pt-4">
                  <AnalysisCard analysis={data.analysis} count={data.analyses_count} />
                </TabsContent>
                <TabsContent value="tweets" className="pt-2">
                  <TweetsList tweets={data.tweets} />
                </TabsContent>
                <TabsContent value="timeline" className="pt-2">
                  <EventFeed events={timeline} showPerson={false} />
                  {data.relations.length > 0 && (
                    <div className="mt-4 space-y-1 text-xs text-muted-foreground">
                      {data.relations.map((r) => (
                        <div key={r.direction}>
                          {r.direction === "follower" ? "Фолловит меня" : "Я фоловлю"}: {r.active ? "да" : "нет"}, впервые{" "}
                          {new Date(r.first_seen_at + "Z").toLocaleDateString("ru-RU")}
                          {r.ended_at && `, закончилось ${new Date(r.ended_at + "Z").toLocaleDateString("ru-RU")}`}
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>
                <TabsContent value="notes" className="pt-4">
                  <Notes personId={id} notes={data.notes} onChanged={refresh} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
        <div className="w-full shrink-0 lg:w-80">
          <ContactCard personId={id} contact={data.contact} onChanged={refresh} />
        </div>
      </div>
    </div>
  );
}
