from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from .types import AccountRef, SourceUser, TweetData, UserProfile


class Source(Protocol):
    """What the rest of the app needs from a Twitter data provider.

    Adapters are read-only. Every method may raise SourceError subclasses;
    transient failures (429/5xx) are retried inside the adapter.
    """

    name: str

    async def me(self, ref: AccountRef) -> UserProfile:
        """My own profile, fresh (used for the follower-count sanity check)."""
        ...

    def iter_followers(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        """Every account following me. May yield ids only."""
        ...

    def iter_following(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        """Every account I follow."""
        ...

    async def get_users(self, ids: list[str]) -> list[UserProfile]:
        """Hydrate profiles by id, any count (adapter chunks)."""
        ...

    async def get_user_by_handle(self, handle: str) -> UserProfile | None: ...

    async def get_user_tweets(
        self, user_id: str, handle: str | None, limit: int, include_replies: bool
    ) -> list[TweetData]:
        """Newest-first, up to `limit` tweets."""
        ...

    async def aclose(self) -> None: ...


class RequestCounter:
    """Shared by adapters so a sync can report how many calls it made."""

    def __init__(self) -> None:
        self.requests = 0
