"""Pydantic DTOs shared by the REST API, the MCP tools and the frontend types."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

Relation = Literal["any", "mutual", "follower_only", "following_only", "follower", "following", "unfollowed_me", "i_unfollowed", "none"]
Stage = Literal["candidate", "followed", "engaged", "followed_back", "no_response", "unfollowed", "lost", "ignored"]
STAGES: tuple[str, ...] = Stage.__args__  # type: ignore[attr-defined]
EventType = Literal[
    "followed_me", "unfollowed_me", "i_followed", "i_unfollowed", "profile_changed", "stage_changed", "note_added", "analyzed"
]
SortKey = Literal[
    "handle", "followers", "-followers", "first_seen", "-first_seen", "last_event", "-last_event", "score", "-score", "deadline", "-deadline"
]


class PeopleFilter(BaseModel):
    """One filter object for the table, the REST API and the MCP tools."""

    q: str | None = Field(None, description="Substring match on handle, name or bio")
    relation: Relation = "any"
    stage: list[Stage] | None = None
    tags: list[str] | None = None
    followers_min: int | None = None
    followers_max: int | None = None
    verified: bool | None = None
    has_analysis: bool | None = None
    score_min: int | None = Field(None, ge=1, le=5)
    persona: list[str] | None = None
    language: str | None = None
    event_type: EventType | None = None
    event_since: datetime | None = Field(None, description="With event_type: people having such an event after this time")
    first_seen_after: datetime | None = None
    last_tweet_after: datetime | None = None
    overdue: bool | None = Field(None, description="Contacts past their follow-back deadline")
    sort: SortKey = "-last_event"
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class TagOut(BaseModel):
    id: int
    name: str
    color: str | None = None


class ContactOut(BaseModel):
    stage: Stage
    followed_at: datetime | None
    engaged_at: datetime | None
    followed_back_at: datetime | None
    deadline_at: datetime | None
    closed_at: datetime | None
    note: str | None
    overdue: bool
    updated_at: datetime


class PersonOut(BaseModel):
    id: str
    handle: str | None
    name: str | None
    bio: str | None
    location: str | None
    url: str | None
    avatar_url: str | None
    followers_count: int | None
    following_count: int | None
    tweets_count: int | None
    verified: bool
    protected: bool
    account_created_at: datetime | None
    first_seen_at: datetime
    profile_synced_at: datetime | None
    is_follower: bool
    is_following: bool
    last_event_at: datetime | None
    last_tweet_at: datetime | None
    tweets_fetched_at: datetime | None
    relevance_score: int | None
    persona: str | None
    primary_language: str | None
    analyzed_at: datetime | None
    stage: Stage | None
    deadline_at: datetime | None
    overdue: bool
    tags: list[TagOut]


class RelationOut(BaseModel):
    direction: str
    active: bool
    first_seen_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None


class EventOut(BaseModel):
    id: int
    person_id: str
    type: str
    at: datetime
    sync_id: int | None
    payload: dict[str, Any] | None
    handle: str | None = None
    name: str | None = None
    avatar_url: str | None = None


class NoteOut(BaseModel):
    id: int
    text: str
    created_at: datetime


class TweetOut(BaseModel):
    id: str
    text: str
    created_at: datetime | None
    lang: str | None
    is_reply: bool
    is_retweet: bool
    is_quote: bool
    url: str | None
    metrics: dict[str, Any] | None


class AnalysisResult(BaseModel):
    """What the model returns. Keep flat and strict: it doubles as the JSON schema."""

    summary: str = Field(description="Who this person is and what they do, 1-2 sentences, in English")
    persona: Literal["founder", "investor", "developer", "marketer", "creator", "company", "bot", "other"]
    topics: list[str] = Field(description="3-6 short topics the person tweets about")
    language: str = Field(description="Primary language of the tweets, ISO 639-1 code")
    relevance_score: int = Field(ge=1, le=5, description="How useful for networking given the user's goal, 1-5")
    relevance_reasons: list[str] = Field(description="2-4 short reasons for the score, in English")
    engagement_style: str = Field(description="How they behave on X: threads, replies, memes, rarely posts, etc.")
    opener: str = Field(description="A hook for a first reply or DM, written in the person's own language")
    red_flags: list[str] = Field(description="Warning signs: bot, spam, sells courses, etc. Empty if none")


class AnalysisOut(BaseModel):
    id: int
    created_at: datetime
    model: str
    prompt_version: str
    tweets_used: int
    result: AnalysisResult
    usage: dict[str, Any] | None


class PersonDetail(BaseModel):
    person: PersonOut
    contact: ContactOut | None
    relations: list[RelationOut]
    notes: list[NoteOut]
    events: list[EventOut]
    tweets: list[TweetOut]
    analysis: AnalysisOut | None
    analyses_count: int


class ContactPatch(BaseModel):
    stage: Stage | None = None
    note: str | None = None
    deadline_at: datetime | None = None
    followed_at: datetime | None = None
    engaged_at: datetime | None = None


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = None


class LookupIn(BaseModel):
    handle: str = Field(min_length=1, max_length=64)
    stage: Stage | None = Field("candidate", description="Pipeline stage to put the person into")


class BulkAction(BaseModel):
    filter: PeopleFilter | None = None
    ids: list[str] | None = None
    action: Literal["fetch_tweets", "analyze", "fetch_and_analyze", "set_stage", "add_tag", "remove_tag", "refresh_profiles"]
    stage: Stage | None = None
    tag: str | None = None
    force: bool = False
    limit: int = Field(500, ge=1, le=5000, description="Safety cap on how many people a bulk action touches")


class SyncOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    source: str
    kind: str
    status: str
    followers_total: int | None
    following_total: int | None
    followers_expected: int | None
    following_expected: int | None
    added_followers: int
    removed_followers: int
    added_following: int
    removed_following: int
    profiles_refreshed: int
    requests: int
    error: str | None
    notes: dict[str, Any] | None


class JobOut(BaseModel):
    id: int
    type: str
    payload: dict[str, Any]
    status: str
    priority: int
    attempts: int
    max_attempts: int
    run_after: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime


class AccountOut(BaseModel):
    user_id: str | None
    handle: str | None
    name: str | None
    avatar_url: str | None
    followers_count: int | None
    following_count: int | None
    synced_at: datetime | None
    history: list[Any] | None


class OverviewOut(BaseModel):
    account: AccountOut | None
    followers: int
    following: int
    mutual: int
    not_following_back: int  # I follow them, they don't follow me
    fans: int  # they follow me, I don't follow them
    waiting: int  # contacts in followed/engaged
    overdue: int
    deltas: dict[str, dict[str, int]]  # {"7d": {"followed_me": n, ...}, "30d": {...}}
    last_sync: SyncOut | None
    next_sync_at: datetime | None
    jobs: dict[str, int]
    recent_events: list[EventOut]
    stages: dict[str, int]


class SettingsOut(BaseModel):
    values: dict[str, Any]  # editable keys, secrets masked
    overrides: list[str]  # which keys come from the DB rather than env
    x: dict[str, Any]
    redirect_uri: str
    sources: list[str]
    stages: list[str]
    configured: dict[str, bool]  # twitterapi, x, anthropic


class SettingsIn(BaseModel):
    values: dict[str, Any]


class SavedViewOut(BaseModel):
    id: int
    name: str
    filter: PeopleFilter
    created_at: datetime


class SavedViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    filter: PeopleFilter


class PipelineOut(BaseModel):
    columns: dict[str, list[PersonOut]]
    counts: dict[str, int]
