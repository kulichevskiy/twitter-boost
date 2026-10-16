// Hand-written mirrors of backend/app/schemas.py. Keep in sync.

export type Relation =
  | "any"
  | "mutual"
  | "follower_only"
  | "following_only"
  | "follower"
  | "following"
  | "unfollowed_me"
  | "i_unfollowed"
  | "none";

export type Stage =
  | "candidate"
  | "followed"
  | "engaged"
  | "followed_back"
  | "no_response"
  | "unfollowed"
  | "lost"
  | "ignored";

export const STAGES: Stage[] = [
  "candidate",
  "followed",
  "engaged",
  "followed_back",
  "no_response",
  "unfollowed",
  "lost",
  "ignored",
];

export type EventType =
  | "followed_me"
  | "unfollowed_me"
  | "i_followed"
  | "i_unfollowed"
  | "profile_changed"
  | "stage_changed"
  | "note_added"
  | "analyzed";

export const EVENT_TYPES: EventType[] = [
  "followed_me",
  "unfollowed_me",
  "i_followed",
  "i_unfollowed",
  "profile_changed",
  "stage_changed",
  "note_added",
  "analyzed",
];

export type SortKey =
  | "handle"
  | "-handle"
  | "followers"
  | "-followers"
  | "tweets"
  | "-tweets"
  | "first_seen"
  | "-first_seen"
  | "last_event"
  | "-last_event"
  | "score"
  | "-score"
  | "deadline";

export type Persona = "founder" | "investor" | "developer" | "marketer" | "creator" | "company" | "bot" | "other";

export interface PeopleFilter {
  q?: string | null;
  relation?: Relation;
  stage?: Stage[] | null;
  tags?: string[] | null;
  followers_min?: number | null;
  followers_max?: number | null;
  verified?: boolean | null;
  has_analysis?: boolean | null;
  score_min?: number | null;
  persona?: string[] | null;
  language?: string | null;
  event_type?: EventType | null;
  event_since?: string | null;
  first_seen_after?: string | null;
  last_tweet_after?: string | null;
  overdue?: boolean | null;
  sort?: SortKey;
  page?: number;
  page_size?: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TagOut {
  id: number;
  name: string;
  color: string | null;
}

export interface ContactOut {
  stage: Stage;
  followed_at: string | null;
  engaged_at: string | null;
  followed_back_at: string | null;
  deadline_at: string | null;
  closed_at: string | null;
  note: string | null;
  overdue: boolean;
  updated_at: string;
}

export interface PersonOut {
  id: string;
  handle: string | null;
  name: string | null;
  bio: string | null;
  location: string | null;
  url: string | null;
  avatar_url: string | null;
  followers_count: number | null;
  following_count: number | null;
  tweets_count: number | null;
  verified: boolean;
  protected: boolean;
  account_created_at: string | null;
  first_seen_at: string;
  profile_synced_at: string | null;
  is_follower: boolean;
  is_following: boolean;
  last_event_at: string | null;
  last_tweet_at: string | null;
  tweets_fetched_at: string | null;
  relevance_score: number | null;
  persona: string | null;
  primary_language: string | null;
  analyzed_at: string | null;
  stage: Stage | null;
  deadline_at: string | null;
  overdue: boolean;
  tags: TagOut[];
}

export interface RelationOut {
  direction: "follower" | "following";
  active: boolean;
  first_seen_at: string;
  last_seen_at: string;
  ended_at: string | null;
}

export interface EventOut {
  id: number;
  person_id: string;
  type: EventType | string;
  at: string;
  sync_id: number | null;
  payload: Record<string, unknown> | null;
  handle?: string | null;
  name?: string | null;
  avatar_url?: string | null;
}

export interface NoteOut {
  id: number;
  text: string;
  created_at: string;
}

export interface TweetOut {
  id: string;
  text: string;
  created_at: string | null;
  lang: string | null;
  is_reply: boolean;
  is_retweet: boolean;
  is_quote: boolean;
  url: string | null;
  metrics: Record<string, number> | null;
}

export interface AnalysisResult {
  summary: string;
  persona: Persona;
  topics: string[];
  language: string;
  relevance_score: number;
  relevance_reasons: string[];
  engagement_style: string;
  opener: string;
  red_flags: string[];
}

export interface AnalysisOut {
  id: number;
  created_at: string;
  model: string;
  prompt_version: string;
  tweets_used: number;
  result: AnalysisResult;
  usage: Record<string, unknown> | null;
}

export interface PersonDetail {
  person: PersonOut;
  contact: ContactOut | null;
  relations: RelationOut[];
  notes: NoteOut[];
  events: EventOut[];
  tweets: TweetOut[];
  analysis: AnalysisOut | null;
  analyses_count: number;
}

export interface ContactPatch {
  stage?: Stage | null;
  note?: string | null;
  deadline_at?: string | null;
  followed_at?: string | null;
  engaged_at?: string | null;
}

export type BulkActionKind =
  | "fetch_tweets"
  | "analyze"
  | "fetch_and_analyze"
  | "set_stage"
  | "add_tag"
  | "remove_tag"
  | "refresh_profiles";

export interface BulkAction {
  filter?: PeopleFilter | null;
  ids?: string[] | null;
  action: BulkActionKind;
  stage?: Stage | null;
  tag?: string | null;
  force?: boolean;
  limit?: number;
}

export type SyncStatus = "running" | "ok" | "suspicious" | "failed";

export interface SyncOut {
  id: number;
  started_at: string;
  finished_at: string | null;
  source: string;
  kind: string;
  status: SyncStatus;
  followers_total: number | null;
  following_total: number | null;
  followers_expected: number | null;
  following_expected: number | null;
  added_followers: number;
  removed_followers: number;
  added_following: number;
  removed_following: number;
  profiles_refreshed: number;
  requests: number;
  error: string | null;
  notes: Record<string, unknown> | null;
}

export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface JobOut {
  id: number;
  type: string;
  payload: Record<string, unknown>;
  status: JobStatus;
  priority: number;
  attempts: number;
  max_attempts: number;
  run_after: string;
  started_at: string | null;
  finished_at: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
}

export interface AccountOut {
  user_id: string | null;
  handle: string | null;
  name: string | null;
  avatar_url: string | null;
  followers_count: number | null;
  following_count: number | null;
  synced_at: string | null;
  history: { at: string; followers: number | null; following: number | null }[] | null;
}

export interface OverviewOut {
  account: AccountOut | null;
  followers: number;
  following: number;
  mutual: number;
  not_following_back: number;
  fans: number;
  waiting: number;
  overdue: number;
  deltas: Record<string, Record<string, number>>;
  last_sync: SyncOut | null;
  next_sync_at: string | null;
  jobs: Record<JobStatus, number>;
  recent_events: EventOut[];
  stages: Record<string, number>;
}

export interface SettingsOut {
  values: Record<string, unknown>;
  overrides: string[];
  x: {
    connected: boolean;
    user_id?: string | null;
    handle?: string | null;
    scopes?: string | null;
    expires_at?: string | null;
    has_refresh_token?: boolean;
  };
  redirect_uri: string;
  sources: string[];
  stages: string[];
  configured: Record<string, boolean>;
}

export interface SavedViewOut {
  id: number;
  name: string;
  filter: PeopleFilter;
  created_at: string;
}

export interface PipelineOut {
  columns: Record<string, PersonOut[]>;
  counts: Record<string, number>;
}
