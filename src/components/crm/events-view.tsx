"use client";

import { useState } from "react";
import useSWR from "swr";
import { ChevronDownIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api, fetcher } from "@/lib/crm/api";
import { EVENT_LABELS } from "@/lib/crm/format";
import type { EventOut, EventType } from "@/lib/crm/types";
import { EVENT_TYPES } from "@/lib/crm/types";
import { BackendAlert } from "./backend-alert";
import { EventFeed } from "./event-feed";

const PRESETS: { value: string; label: string; hours: number | null }[] = [
  { value: "24h", label: "24h", hours: 24 },
  { value: "7d", label: "7d", hours: 24 * 7 },
  { value: "30d", label: "30d", hours: 24 * 30 },
  { value: "all", label: "All", hours: null },
];

function sinceFor(preset: string): string | null {
  const hours = PRESETS.find((p) => p.value === preset)?.hours ?? null;
  return hours ? new Date(Date.now() - hours * 3600_000).toISOString().replace("Z", "") : null;
}

export function EventsView() {
  const [types, setTypes] = useState<EventType[]>([]);
  const [preset, setPresetState] = useState("7d");
  const [since, setSince] = useState<string | null>(() => sinceFor("7d"));
  const setPreset = (v: string) => {
    setPresetState(v);
    setSince(sinceFor(v));
  };
  const [extra, setExtra] = useState<EventOut[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exhausted, setExhausted] = useState(false);

  const qs = new URLSearchParams({ limit: "100" });
  if (since) qs.set("since", since);
  if (types.length) qs.set("type", types.join(","));
  const key = `/events?${qs.toString()}`;
  const { data, error, isLoading } = useSWR<EventOut[]>(key, fetcher, {
    onSuccess: () => {
      setExtra([]);
      setExhausted(false);
    },
  });

  const all = [...(data ?? []), ...extra];
  const loadMore = async () => {
    const last = all[all.length - 1];
    if (!last) return;
    setLoadingMore(true);
    try {
      const more = await api.get<EventOut[]>(`${key}&before_id=${last.id}`);
      setExtra((x) => [...x, ...more]);
      if (more.length < 100) setExhausted(true);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Events</h1>
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button size="sm" variant="outline" />}>
              {types.length ? `Types: ${types.length}` : "All types"} <ChevronDownIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              {EVENT_TYPES.map((t) => (
                <DropdownMenuCheckboxItem
                  key={t}
                  checked={types.includes(t)}
                  closeOnClick={false}
                  onCheckedChange={(c) => setTypes((x) => (c ? [...x, t] : x.filter((y) => y !== t)))}
                >
                  {EVENT_LABELS[t]}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <ToggleGroup value={[preset]} onValueChange={(v) => v[0] && setPreset(String(v[0]))} variant="outline" size="sm">
            {PRESETS.map((p) => (
              <ToggleGroupItem key={p.value} value={p.value}>
                {p.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
      </div>
      {error ? (
        <BackendAlert error={error} />
      ) : isLoading && !data ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : (
        <div className="rounded-xl px-4 ring-1 ring-foreground/10">
          <EventFeed events={all} />
          {data && data.length >= 100 && !exhausted && (
            <div className="py-3 text-center">
              <Button size="sm" variant="outline" disabled={loadingMore} onClick={() => void loadMore()}>
                Show more
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
