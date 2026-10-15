import type { EventType, Relation, SortKey, Stage } from "./types";

const rtf = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });

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
  if (abs < 60) return "только что";
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
  if (abs < 86400 * 365) return rtf.format(Math.round(diff / (86400 * 30)), "month");
  return rtf.format(Math.round(diff / (86400 * 365)), "year");
}

export function formatDate(value: string | null | undefined, withTime = false): string {
  const d = parseDate(value);
  if (!d) return "—";
  return d.toLocaleString("ru-RU", {
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
  return new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function duration(start: string | null, end: string | null): string {
  const a = parseDate(start);
  const b = parseDate(end);
  if (!a || !b) return "—";
  const s = Math.round((b.getTime() - a.getTime()) / 1000);
  if (s < 60) return `${s} с`;
  return `${Math.floor(s / 60)} мин ${s % 60} с`;
}

export const STAGE_LABELS: Record<Stage, string> = {
  candidate: "Кандидат",
  followed: "Зафоловил",
  engaged: "Общаюсь",
  followed_back: "Взаимно",
  no_response: "Без ответа",
  unfollowed: "Отфоловил",
  lost: "Отписался",
  ignored: "Игнор",
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
  followed_me: "подписался на меня",
  unfollowed_me: "отписался от меня",
  i_followed: "я подписался",
  i_unfollowed: "я отписался",
  profile_changed: "изменил профиль",
  stage_changed: "стадия изменена",
  note_added: "заметка",
  analyzed: "разобран",
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
  any: "Все",
  mutual: "Взаимные",
  follower_only: "Только фолловят меня",
  following_only: "Только я фоловлю",
  follower: "Фолловят меня",
  following: "Я фоловлю",
  unfollowed_me: "Отписались от меня",
  i_unfollowed: "Я отписался",
  none: "Нет связи",
};

export const SORT_LABELS: Record<SortKey, string> = {
  "-last_event": "Последнее событие",
  last_event: "Давнее событие",
  "-followers": "Фолловеров: больше",
  followers: "Фолловеров: меньше",
  "-score": "Оценка: выше",
  score: "Оценка: ниже",
  "-first_seen": "Новые",
  first_seen: "Старые",
  handle: "По хендлу",
  deadline: "По дедлайну",
};

export const PERSONA_LABELS: Record<string, string> = {
  founder: "Фаундер",
  investor: "Инвестор",
  developer: "Разработчик",
  marketer: "Маркетолог",
  creator: "Создатель контента",
  company: "Компания",
  bot: "Бот",
  other: "Другое",
};

export function personaLabel(p: string | null | undefined): string {
  if (!p) return "—";
  return PERSONA_LABELS[p] ?? p;
}

export const JOB_LABELS: Record<string, string> = {
  sync_full: "Синк списков",
  fetch_tweets: "Твиты",
  analyze: "Анализ",
  fetch_and_analyze: "Твиты + анализ",
  refresh_profiles: "Профили",
  lookup: "Поиск по хендлу",
  bulk: "Массовое действие",
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
