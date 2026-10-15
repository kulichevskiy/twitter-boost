"""Provider-neutral shapes every source adapter maps into."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class UserProfile:
    id: str
    handle: str | None = None
    name: str | None = None
    bio: str | None = None
    location: str | None = None
    url: str | None = None
    avatar_url: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    tweets_count: int | None = None
    verified: bool = False
    protected: bool = False
    created_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceUser:
    """A list member. `profile` is present when the list endpoint returns full
    objects (X API, twitterapi followings) and None when only ids come back
    (twitterapi followers_ids)."""

    id: str
    profile: UserProfile | None = None


@dataclass(slots=True)
class TweetData:
    id: str
    text: str
    created_at: datetime | None
    lang: str | None = None
    is_reply: bool = False
    is_retweet: bool = False
    is_quote: bool = False
    url: str | None = None
    metrics: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccountRef:
    """Who we are. Adapters need the id (X API) or the handle (twitterapi.io)."""

    id: str | None
    handle: str | None


class SourceError(Exception):
    """Base for adapter failures."""


class OutOfCredits(SourceError):
    """Provider balance exhausted: do not retry."""


class NotConfigured(SourceError):
    """Adapter is selected but credentials are missing."""


class RateLimited(SourceError):
    def __init__(self, retry_after: float, message: str = "rate limited"):
        super().__init__(message)
        self.retry_after = retry_after
