from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Person(Base):
    """Anyone we have seen: a follower, someone we follow, or a manual lookup."""

    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # X user id as string
    handle: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    bio: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(String(512))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    tweets_count: Mapped[int | None] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    account_created_at: Mapped[datetime | None] = mapped_column(DateTime)
    profile_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_tweet_at: Mapped[datetime | None] = mapped_column(DateTime)
    tweets_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Denormalised for cheap filtering/sorting; maintained by sync and analysis.
    is_follower: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_following: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    relevance_score: Mapped[int | None] = mapped_column(Integer, index=True)
    persona: Mapped[str | None] = mapped_column(String(32), index=True)
    primary_language: Mapped[str | None] = mapped_column(String(8))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)

    relations: Mapped[list[Relation]] = relationship(back_populates="person", cascade="all, delete-orphan")
    contact: Mapped[Contact | None] = relationship(
        back_populates="person", uselist=False, cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(secondary="person_tags", back_populates="people")


class Relation(Base):
    """Membership of a person in one of my two lists."""

    __tablename__ = "relations"
    __table_args__ = (UniqueConstraint("person_id", "direction", name="uq_relation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(16), index=True)  # follower | following
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    missing_streak: Mapped[int] = mapped_column(Integer, default=0)

    person: Mapped[Person] = relationship(back_populates="relations")


class Sync(Base):
    __tablename__ = "syncs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16), default="full")  # baseline | full
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|ok|suspicious|failed
    followers_total: Mapped[int | None] = mapped_column(Integer)
    following_total: Mapped[int | None] = mapped_column(Integer)
    followers_expected: Mapped[int | None] = mapped_column(Integer)
    following_expected: Mapped[int | None] = mapped_column(Integer)
    added_followers: Mapped[int] = mapped_column(Integer, default=0)
    removed_followers: Mapped[int] = mapped_column(Integer, default=0)
    added_following: Mapped[int] = mapped_column(Integer, default=0)
    removed_following: Mapped[int] = mapped_column(Integer, default=0)
    profiles_refreshed: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Snapshot(Base):
    """Full membership list per sync and direction, zstd-compressed ids."""

    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(16))
    count: Mapped[int] = mapped_column(Integer)
    ids_blob: Mapped[bytes] = mapped_column(LargeBinary)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_person_at", "person_id", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    sync_id: Mapped[int | None] = mapped_column(ForeignKey("syncs.id", ondelete="SET NULL"))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    person: Mapped[Person] = relationship()


class Contact(Base):
    """CRM state of a person in my networking pipeline."""

    __tablename__ = "contacts"

    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    followed_at: Mapped[datetime | None] = mapped_column(DateTime)
    engaged_at: Mapped[datetime | None] = mapped_column(DateTime)
    followed_back_at: Mapped[datetime | None] = mapped_column(DateTime)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    person: Mapped[Person] = relationship(back_populates="contact")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    color: Mapped[str | None] = mapped_column(String(16))

    people: Mapped[list[Person]] = relationship(secondary="person_tags", back_populates="tags")


class PersonTag(Base):
    __tablename__ = "person_tags"

    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Tweet(Base):
    __tablename__ = "tweets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    lang: Mapped[str | None] = mapped_column(String(8))
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    is_retweet: Mapped[bool] = mapped_column(Boolean, default=False)
    is_quote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str | None] = mapped_column(String(256))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    tweets_used: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_run_after", "status", "run_after"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed|cancelled
    priority: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SavedView(Base):
    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    filter: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class XToken(Base):
    """OAuth 2.0 user token for the official X API. Single row (id=1)."""

    __tablename__ = "x_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    scopes: Mapped[str | None] = mapped_column(String(256))
    user_id: Mapped[str | None] = mapped_column(String(32))
    handle: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Setting(Base):
    """Key/value overrides of app/config.py, edited from the UI."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Account(Base):
    """My own profile as last seen by the source. Single row (id=1)."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    user_id: Mapped[str | None] = mapped_column(String(32))
    handle: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(256))
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Rolling history of my counters, one point per sync: [{at, followers, following}]
    history: Mapped[list[Any] | None] = mapped_column(JSON)
