import { ExternalLinkIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { compact, formatDate } from "@/lib/crm/format";
import type { TweetOut } from "@/lib/crm/types";

export function TweetsList({ tweets }: { tweets: TweetOut[] }) {
  if (!tweets.length) return <p className="text-sm text-muted-foreground">Твиты ещё не загружены. Нажми «Обновить твиты».</p>;
  return (
    <ul className="divide-y">
      {tweets.map((t) => (
        <li key={t.id} className="space-y-1 py-3 text-sm">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="tabular-nums">{formatDate(t.created_at, true)}</span>
            {t.is_reply && <Badge variant="outline">reply</Badge>}
            {t.is_quote && <Badge variant="outline">quote</Badge>}
            {t.is_retweet && <Badge variant="outline">RT</Badge>}
            {t.lang && <span>{t.lang}</span>}
            {t.url && (
              <a href={t.url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 hover:underline">
                открыть <ExternalLinkIcon className="size-3" />
              </a>
            )}
          </div>
          <p className="whitespace-pre-line">{t.text}</p>
          {t.metrics && (
            <div className="flex gap-3 text-xs text-muted-foreground tabular-nums">
              <span>♥ {compact(t.metrics.likes)}</span>
              <span>↻ {compact(t.metrics.retweets)}</span>
              <span>💬 {compact(t.metrics.replies)}</span>
              {t.metrics.views ? <span>👁 {compact(t.metrics.views)}</span> : null}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
