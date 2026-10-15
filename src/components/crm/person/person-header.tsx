"use client";

import { useState } from "react";
import { BadgeCheckIcon, ExternalLinkIcon, LockIcon, PlusIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api } from "@/lib/crm/api";
import { compact, formatDate, relativeTime } from "@/lib/crm/format";
import type { PersonOut, TagOut } from "@/lib/crm/types";
import { PersonAvatar } from "../person-avatar";
import { RelationBadges, ScoreDots } from "../badges";

export function PersonHeader({ person, onChanged }: { person: PersonOut; onChanged: () => void }) {
  const [tag, setTag] = useState("");
  const [open, setOpen] = useState(false);

  const addTag = async () => {
    const name = tag.trim();
    if (!name) return;
    try {
      await api.post<TagOut[]>(`/people/${person.id}/tags`, { name });
      setTag("");
      setOpen(false);
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Ошибка");
    }
  };
  const removeTag = async (name: string) => {
    await api.del(`/people/${person.id}/tags/${encodeURIComponent(name)}`);
    onChanged();
  };

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
      <PersonAvatar src={person.avatar_url} name={person.name} handle={person.handle} className="size-16 text-base" />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{person.name ?? `@${person.handle ?? person.id}`}</h1>
          {person.verified && <BadgeCheckIcon className="size-4 text-blue-500" />}
          {person.protected && <LockIcon className="size-4 text-muted-foreground" />}
          {person.handle && (
            <a
              href={`https://x.com/${person.handle}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline"
            >
              @{person.handle} <ExternalLinkIcon className="size-3" />
            </a>
          )}
        </div>
        {person.bio && <p className="text-sm whitespace-pre-line">{person.bio}</p>}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground tabular-nums">
          <span>
            <b className="text-foreground">{compact(person.followers_count)}</b> фолловеров
          </span>
          <span>
            <b className="text-foreground">{compact(person.following_count)}</b> подписок
          </span>
          <span>
            <b className="text-foreground">{compact(person.tweets_count)}</b> твитов
          </span>
          {person.location && <span>{person.location}</span>}
          {person.url && (
            <a href={person.url} target="_blank" rel="noreferrer" className="truncate hover:underline">
              {person.url.replace(/^https?:\/\//, "")}
            </a>
          )}
          {person.account_created_at && <span>в X с {formatDate(person.account_created_at)}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <RelationBadges isFollower={person.is_follower} isFollowing={person.is_following} />
          {person.relevance_score !== null && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <ScoreDots score={person.relevance_score} /> оценка
            </span>
          )}
          <span className="text-xs text-muted-foreground">в базе {relativeTime(person.first_seen_at)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {person.tags.map((t) => (
            <Badge key={t.id} variant="outline" className="gap-1 pr-1">
              {t.name}
              <button type="button" onClick={() => void removeTag(t.name)} aria-label={`Убрать тег ${t.name}`} className="rounded hover:bg-muted">
                <XIcon className="size-3" />
              </button>
            </Badge>
          ))}
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger render={<Button size="xs" variant="ghost" />}>
              <PlusIcon /> тег
            </PopoverTrigger>
            <PopoverContent className="w-56 p-2">
              <form
                className="flex gap-1"
                onSubmit={(e) => {
                  e.preventDefault();
                  void addTag();
                }}
              >
                <Input autoFocus value={tag} onChange={(e) => setTag(e.target.value)} placeholder="название" className="h-7 text-[0.8rem]" />
                <Button size="sm" type="submit">
                  Ок
                </Button>
              </form>
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </div>
  );
}
