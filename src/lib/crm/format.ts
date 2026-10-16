import type { EventType, Relation, SortKey, Stage } from "./types";

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** Backend stores naive UTC timestamps without a zone suffix. */
export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const iso = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function relativeTime(value: string | null | undefined, now = Date.now()): string {
  const d = parseDate(value);
  if (!d) return "—";
  const diff = (d.getTime() - now) / 1000;
  const abs = Math.abs(diff);
  if (abs < 60) return "just now";
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
  if (abs < 86400 * 365) return rtf.format(Math.round(diff / (86400 * 30)), "month");
  return rtf.format(Math.round(diff / (86400 * 365)), "year");
}

export function formatDate(value: string | null | undefined, withTime = false): string {
  const d = parseDate(value);
  if (!d) return "—";
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function daysSince(value: string | null | undefined, now = Date.now()): number | null {
  const d = parseDate(value);
  if (!d) return null;
  return Math.floor((now - d.getTime()) / 86400_000);
}

export function daysUntil(value: string | null | undefined, now = Date.now()): number | null {
  const d = parseDate(value);
  if (!d) return null;
  return Math.ceil((d.getTime() - now) / 86400_000);
}

export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function duration(start: string | null, end: string | null): string {
  const a = parseDate(start);
  const b = parseDate(end);
  if (!a || !b) return "—";
  const s = Math.round((b.getTime() - a.getTime()) / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export const STAGE_LABELS: Record<Stage, string> = {
  candidate: "Candidate",
  followed: "Followed",
  engaged: "Engaged",
  followed_back: "Followed back",
  no_response: "No response",
  unfollowed: "Unfollowed",
  lost: "Lost",
  ignored: "Ignored",
};

export const STAGE_CLASSES: Record<Stage, string> = {
  candidate: "bg-muted text-muted-foreground",
  followed: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  engaged: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
  followed_back: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  no_response: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  unfollowed: "bg-muted text-muted-foreground line-through",
  lost: "bg-red-500/10 text-red-700 dark:text-red-300",
  ignored: "bg-muted text-muted-foreground",
};

export const EVENT_LABELS: Record<EventType, string> = {
  followed_me: "followed me",
  unfollowed_me: "unfollowed me",
  i_followed: "I followed",
  i_unfollowed: "I unfollowed",
  profile_changed: "profile changed",
  stage_changed: "stage changed",
  note_added: "note added",
  analyzed: "analyzed",
};

export const EVENT_CLASSES: Partial<Record<EventType, string>> = {
  followed_me: "text-emerald-700 dark:text-emerald-300",
  unfollowed_me: "text-red-700 dark:text-red-300",
  i_followed: "text-blue-700 dark:text-blue-300",
  i_unfollowed: "text-muted-foreground",
};

export function eventLabel(type: string): string {
  return (EVENT_LABELS as Record<string, string>)[type] ?? type;
}

export const RELATION_LABELS: Record<Relation, string> = {
  any: "All",
  mutual: "Mutual",
  follower_only: "Follow me only",
  following_only: "I follow only",
  follower: "Follow me",
  following: "I follow",
  unfollowed_me: "Unfollowed me",
  i_unfollowed: "I unfollowed",
  none: "No relation",
};

export const SORT_LABELS: Record<SortKey, string> = {
  "-last_event": "Latest event",
  last_event: "Oldest event",
  "-followers": "Most followers",
  followers: "Fewest followers",
  "-score": "Highest score",
  score: "Lowest score",
  "-first_seen": "Newest",
  first_seen: "Oldest",
  handle: "Handle A–Z",
  "-handle": "Handle Z–A",
  deadline: "By deadline",
};

export const PERSONA_LABELS: Record<string, string> = {
  founder: "Founder",
  investor: "Investor",
  developer: "Developer",
  marketer: "Marketer",
  creator: "Creator",
  company: "Company",
  bot: "Bot",
  other: "Other",
};

export function personaLabel(p: string | null | undefined): string {
  if (!p) return "—";
  return PERSONA_LABELS[p] ?? p;
}

export const JOB_LABELS: Record<string, string> = {
  sync_full: "List sync",
  fetch_tweets: "Tweets",
  analyze: "Analysis",
  fetch_and_analyze: "Tweets + analysis",
  refresh_profiles: "Profiles",
  lookup: "Handle lookup",
  bulk: "Bulk action",
};

export function jobLabel(type: string): string {
  return JOB_LABELS[type] ?? type;
}

export function initials(name: string | null | undefined, handle: string | null | undefined): string {
  const src = (name || handle || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}
