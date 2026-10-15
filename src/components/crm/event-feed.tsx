import Link from "next/link";
import { PersonAvatar } from "./person-avatar";
import { EVENT_CLASSES, eventLabel, relativeTime, STAGE_LABELS } from "@/lib/crm/format";
import type { EventOut, EventType, Stage } from "@/lib/crm/types";
import { cn } from "cn";

function describe(e: EventOut): string {
  const p = e.payload ?? {};
  if (e.type === "stage_changed") {
    const to = STAGE_LABELS[p.to as Stage] ?? String(p.to ?? "");
    const from = STAGE_LABELS[p.from as Stage] ?? String(p.from ?? "");
    return `стадия: ${from || "—"} → ${to}`;
  }
  if (e.type === "profile_changed") {
    return `изменил ${Object.keys(p).join(", ")}`;
  }
  if (e.type === "note_added") return `заметка: ${String(p.preview ?? "")}`;
  if (e.type === "analyzed") return `разобран, оценка ${String(p.score ?? "?")}`;
  if (p.again) return `${eventLabel(e.type)} (снова)`;
  return eventLabel(e.type);
}

export function EventFeed({ events, showPerson = true, className }: { events: EventOut[]; showPerson?: boolean; className?: string }) {
  if (!events.length) return <p className="text-sm text-muted-foreground">Событий пока нет.</p>;
  return (
    <ul className={cn("divide-y", className)}>
      {events.map((e) => (
        <li key={e.id} className="flex items-start gap-3 py-2 text-sm">
          {showPerson && <PersonAvatar src={e.avatar_url} name={e.name} handle={e.handle} className="mt-0.5 size-7" />}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2">
              {showPerson && (
                <Link href={`/crm/people/${e.person_id}`} className="font-medium hover:underline">
                  @{e.handle ?? e.person_id}
                </Link>
              )}
              <span className={cn(EVENT_CLASSES[e.type as EventType])}>{describe(e)}</span>
            </div>
          </div>
          <time className="shrink-0 text-xs text-muted-foreground tabular-nums" title={e.at}>
            {relativeTime(e.at)}
          </time>
        </li>
      ))}
    </ul>
  );
}
