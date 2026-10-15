"""Official X API v2 adapter, OAuth 2.0 user context.

Reads of my own followers/following are "owned reads" ($0.001 each). Other
users' posts are $0.005 each, profiles $0.010 each, so by default this adapter
only serves the list operations; see sources/registry.py.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from .base import RequestCounter
from .types import AccountRef, NotConfigured, RateLimited, SourceError, SourceUser, TweetData, UserProfile

log = logging.getLogger(__name__)

USER_FIELDS = "id,username,name,description,location,url,profile_image_url,public_metrics,verified,verified_type,protected,created_at"
POST_FIELDS = "id,text,created_at,lang,public_metrics,referenced_tweets,conversation_id,in_reply_to_user_id"

TokenGetter = Callable[[], Awaitable[str]]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return None


def profile_from_x(u: dict[str, Any]) -> UserProfile:
    m = u.get("public_metrics") or {}
    avatar = u.get("profile_image_url")
    if avatar:
        avatar = avatar.replace("_normal.", "_400x400.")
    return UserProfile(
        id=str(u["id"]),
        handle=u.get("username"),
        name=u.get("name"),
        bio=u.get("description"),
        location=u.get("location"),
        url=u.get("url"),
        avatar_url=avatar,
        followers_count=m.get("followers_count"),
        following_count=m.get("following_count"),
        tweets_count=m.get("post_count", m.get("tweet_count")),
        verified=bool(u.get("verified")) or (u.get("verified_type") not in (None, "none", "")),
        protected=bool(u.get("protected")),
        created_at=_parse_dt(u.get("created_at")),
        raw=u,
    )


def tweet_from_x(t: dict[str, Any], handle: str | None) -> TweetData:
    m = t.get("public_metrics") or {}
    refs = {r.get("type") for r in (t.get("referenced_tweets") or [])}
    tid = str(t["id"])
    return TweetData(
        id=tid,
        text=t.get("text") or "",
        created_at=_parse_dt(t.get("created_at")),
        lang=t.get("lang"),
        is_reply="replied_to" in refs,
        is_retweet="retweeted" in refs,
        is_quote="quoted" in refs,
        url=f"https://x.com/{handle}/status/{tid}" if handle else f"https://x.com/i/status/{tid}",
        metrics={
            "likes": m.get("like_count", 0),
            "retweets": m.get("repost_count", m.get("retweet_count", 0)),
            "replies": m.get("reply_count", 0),
            "quotes": m.get("quote_count", 0),
            "views": m.get("impression_count", 0),
            "bookmarks": m.get("bookmark_count", 0),
        },
        raw=t,
    )


class XOfficialSource:
    name = "x"

    def __init__(
        self,
        get_token: TokenGetter,
        base_url: str = "https://api.x.com",
        counter: RequestCounter | None = None,
        client: httpx.AsyncClient | None = None,
        max_rate_limit_wait: float = 900.0,
    ) -> None:
        self._get_token = get_token
        self.counter = counter or RequestCounter()
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(30.0, connect=10.0))
        self._max_wait = max_rate_limit_wait

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        delay = 1.0
        for _attempt in range(6):
            token = await self._get_token()
            if not token:
                raise NotConfigured("X account is not connected")
            self.counter.requests += 1
            try:
                resp = await self._client.get(
                    path, params=params, headers={"authorization": f"Bearer {token}"}
                )
            except httpx.TransportError as exc:
                log.warning("x api transport error on %s: %s", path, exc)
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if resp.status_code == 429:
                reset = resp.headers.get("x-rate-limit-reset")
                wait = max(5.0, float(reset) - time.time() + 1) if reset else delay
                if wait > self._max_wait:
                    raise RateLimited(wait, f"X API rate limit on {path}, resets in {wait:.0f}s")
                log.info("x api 429 on %s, sleeping %.0fs", path, wait)
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 500:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            if resp.status_code == 401:
                # token may have just been refreshed by another call; retry once
                if _attempt == 0:
                    continue
                raise SourceError(f"X API unauthorized: {resp.text[:300]}")
            if resp.status_code >= 400:
                raise SourceError(f"X API {path}: HTTP {resp.status_code} {resp.text[:300]}")
            return resp.json()
        raise SourceError(f"X API {path}: gave up after retries")

    async def me(self, ref: AccountRef) -> UserProfile:
        data = await self._get("/2/users/me", {"user.fields": USER_FIELDS})
        return profile_from_x(data["data"])

    async def _iter_list(self, ref: AccountRef, kind: str) -> AsyncIterator[SourceUser]:
        if not ref.id:
            raise NotConfigured("account id required for X API")
        token: str | None = None
        seen: set[str] = set()
        while True:
            params: dict[str, Any] = {"max_results": 1000, "user.fields": USER_FIELDS}
            if token:
                params["pagination_token"] = token
            data = await self._get(f"/2/users/{ref.id}/{kind}", params)
            for u in data.get("data") or []:
                p = profile_from_x(u)
                if p.id in seen:
                    continue
                seen.add(p.id)
                yield SourceUser(id=p.id, profile=p)
            token = (data.get("meta") or {}).get("next_token")
            if not token:
                break

    def iter_followers(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        return self._iter_list(ref, "followers")

    def iter_following(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        return self._iter_list(ref, "following")

    async def get_users(self, ids: list[str]) -> list[UserProfile]:
        out: list[UserProfile] = []
        for i in range(0, len(ids), 100):
            chunk = ids[i : i + 100]
            data = await self._get("/2/users", {"ids": ",".join(chunk), "user.fields": USER_FIELDS})
            out.extend(profile_from_x(u) for u in data.get("data") or [])
        return out

    async def get_user_by_handle(self, handle: str) -> UserProfile | None:
        try:
            data = await self._get(f"/2/users/by/username/{handle.lstrip('@')}", {"user.fields": USER_FIELDS})
        except SourceError as exc:
            if "404" in str(exc):
                return None
            raise
        u = data.get("data")
        return profile_from_x(u) if u else None

    async def get_user_tweets(
        self, user_id: str, handle: str | None, limit: int, include_replies: bool
    ) -> list[TweetData]:
        out: list[TweetData] = []
        token: str | None = None
        while len(out) < limit:
            params: dict[str, Any] = {
                "max_results": max(5, min(100, limit - len(out))),
                "tweet.fields": POST_FIELDS,
                "exclude": "retweets" if include_replies else "retweets,replies",
            }
            if token:
                params["pagination_token"] = token
            data = await self._get(f"/2/users/{user_id}/tweets", params)
            tweets = data.get("data") or []
            out.extend(tweet_from_x(t, handle) for t in tweets)
            token = (data.get("meta") or {}).get("next_token")
            if not tweets or not token:
                break
        return out[:limit]
