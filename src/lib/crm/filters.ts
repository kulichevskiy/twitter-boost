import type { EventType, PeopleFilter, Relation, SortKey, Stage } from "./types";

const ARRAY_KEYS = ["stage", "tags", "persona"] as const;
const NUMBER_KEYS = ["followers_min", "followers_max", "score_min", "page", "page_size"] as const;
const BOOL_KEYS = ["verified", "has_analysis", "overdue"] as const;
const STRING_KEYS = ["q", "language", "event_since", "first_seen_after", "last_tweet_after"] as const;

export const DEFAULT_FILTER: PeopleFilter = { relation: "any", sort: "-last_event", page: 1, page_size: 50 };

export function parseFilter(sp: URLSearchParams): PeopleFilter {
  const f: PeopleFilter = { ...DEFAULT_FILTER };
  for (const k of STRING_KEYS) {
    const v = sp.get(k);
    if (v) f[k] = v;
  }
  for (const k of NUMBER_KEYS) {
    const v = sp.get(k);
    if (v !== null && v !== "" && !Number.isNaN(Number(v))) f[k] = Number(v);
  }
  for (const k of BOOL_KEYS) {
    const v = sp.get(k);
    if (v === "true") f[k] = true;
    else if (v === "false") f[k] = false;
  }
  for (const k of ARRAY_KEYS) {
    const v = sp.getAll(k);
    if (v.length) f[k] = v as Stage[] & string[];
  }
  const relation = sp.get("relation");
  if (relation) f.relation = relation as Relation;
  const sort = sp.get("sort");
  if (sort) f.sort = sort as SortKey;
  const eventType = sp.get("event_type");
  if (eventType) f.event_type = eventType as EventType;
  return f;
}

export function serializeFilter(f: PeopleFilter): URLSearchParams {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v === undefined || v === null || v === "") continue;
    if (k in DEFAULT_FILTER && DEFAULT_FILTER[k as keyof PeopleFilter] === v) continue;
    if (Array.isArray(v)) {
      for (const item of v) sp.append(k, String(item));
    } else {
      sp.set(k, String(v));
    }
  }
  return sp;
}

export function countActive(f: PeopleFilter): number {
  let n = 0;
  for (const [k, v] of Object.entries(f)) {
    if (k === "page" || k === "page_size" || k === "sort") continue;
    if (v === undefined || v === null || v === "" || (k === "relation" && v === "any")) continue;
    if (Array.isArray(v) && v.length === 0) continue;
    n++;
  }
  return n;
}
