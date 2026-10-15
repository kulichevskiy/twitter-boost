"""twitterapi.io adapter (https://docs.twitterapi.io).

Cheapest path for lists: followers via /followers_ids (5000 ids per call),
followings via /followings (200 full profiles per call), new profiles via
/batch_info_by_ids (1 credit per user from 100+). Tweets via /last_tweets.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .base import RequestCounter
from .types import (
    AccountRef,
    NotConfigured,
    OutOfCredits,
    SourceError,
    SourceUser,
    TweetData,
    UserProfile,
)

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # "Wed Dec 19 20:20:32 +0000 2007"
        return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y").astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).astimezone(UTC).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def profile_from_camel(u: dict[str, Any]) -> UserProfile:
    """UserInfo schema: /user/info, /batch_info_by_ids, tweet.author."""
    return UserProfile(
        id=str(u["id"]),
        handle=u.get("userName") or u.get("screen_name"),
        name=u.get("name"),
        bio=u.get("description") or (u.get("profile_bio") or {}).get("description"),
        location=u.get("location") or None,
        url=u.get("url"),
        avatar_url=u.get("profilePicture"),
        followers_count=u.get("followers"),
        following_count=u.get("following"),
        tweets_count=u.get("statusesCount"),
        verified=bool(u.get("isBlueVerified")),
        protected=bool(u.get("protected", False)),
        created_at=_parse_dt(u.get("createdAt")),
        raw=u,
    )


def profile_from_snake(u: dict[str, Any]) -> UserProfile:
    """UserProfileSnake schema: /followers, /followings."""
    return UserProfile(
        id=str(u["id"]),
        handle=u.get("screen_name") or u.get("userName") or u.get("username"),
        name=u.get("name"),
        bio=u.get("description"),
        location=u.get("location") or None,
        url=u.get("url"),
        avatar_url=u.get("profile_image_url_https"),
        followers_count=u.get("followers_count"),
        following_count=u.get("following_count", u.get("friends_count")),
        tweets_count=u.get("statuses_count"),
        verified=bool(u.get("isBlueVerified") or u.get("verified")),
        protected=bool(u.get("protected", False)),
        created_at=_parse_dt(u.get("created_at")),
        raw=u,
    )


def tweet_from_api(t: dict[str, Any]) -> TweetData:
    return TweetData(
        id=str(t["id"]),
        text=t.get("text") or "",
        created_at=_parse_dt(t.get("createdAt")),
        lang=t.get("lang") or None,
        is_reply=bool(t.get("isReply")),
        is_retweet=t.get("retweeted_tweet") is not None,
        is_quote=t.get("quoted_tweet") is not None,
        url=t.get("url"),
        metrics={
            "likes": t.get("likeCount") or 0,
            "retweets": t.get("retweetCount") or 0,
            "replies": t.get("replyCount") or 0,
            "quotes": t.get("quoteCount") or 0,
            "views": t.get("viewCount") or 0,
            "bookmarks": t.get("bookmarkCount") or 0,
        },
        raw=t,
    )


class TwitterApiIoSource:
    name = "twitterapi"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.twitterapi.io",
        counter: RequestCounter | None = None,
        max_concurrency: int = 4,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise NotConfigured("TWITTERAPI_IO_KEY is not set")
        self.counter = counter or RequestCounter()
        self._sem = asyncio.Semaphore(max_concurrency)
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ http
    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        delay = 1.0
        for attempt in range(6):
            async with self._sem:
                self.counter.requests += 1
                try:
                    resp = await self._client.get(path, params=clean)
                except httpx.TransportError as exc:
                    log.warning("twitterapi transport error on %s: %s", path, exc)
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
            if resp.status_code == 402:
                raise OutOfCredits("twitterapi.io: credits exhausted, top up at https://twitterapi.io/dashboard")
            if resp.status_code in RETRY_STATUSES:
                log.info("twitterapi %s -> %s, retry in %.1fs", path, resp.status_code, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            if resp.status_code >= 400:
                raise SourceError(f"twitterapi.io {path}: HTTP {resp.status_code} {resp.text[:300]}")
            data = resp.json()
            if isinstance(data, dict) and data.get("status") == "error":
                msg = data.get("msg") or data.get("message") or "error"
                raise SourceError(f"twitterapi.io {path}: {msg}")
            return data
        raise SourceError(f"twitterapi.io {path}: gave up after retries")

    # ------------------------------------------------------------------ api
    async def me(self, ref: AccountRef) -> UserProfile:
        if not ref.handle:
            raise NotConfigured("MY_HANDLE is required for twitterapi.io")
        data = await self._get("/twitter/user/info", {"userName": ref.handle})
        return profile_from_camel(data["data"])

    async def iter_followers(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        params: dict[str, Any] = {"count": 5000}
        if ref.id:
            params["userId"] = ref.id
        elif ref.handle:
            params["userName"] = ref.handle
        else:
            raise NotConfigured("account id or handle required")
        cursor = ""
        seen: set[str] = set()
        while True:
            data = await self._get("/twitter/user/followers_ids", {**params, "cursor": cursor})
            for uid in data.get("ids") or []:
                uid = str(uid)
                if uid in seen:
                    continue
                seen.add(uid)
                yield SourceUser(id=uid)
            cursor = data.get("next_cursor") or ""
            if not data.get("has_next_page") or cursor in ("", "0"):
                break

    async def iter_following(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        if not ref.handle:
            raise NotConfigured("MY_HANDLE is required for twitterapi.io")
        cursor = ""
        seen: set[str] = set()
        while True:
            data = await self._get(
                "/twitter/user/followings", {"userName": ref.handle, "pageSize": 200, "cursor": cursor}
            )
            for u in data.get("followings") or []:
                p = profile_from_snake(u)
                if p.id in seen:
                    continue
                seen.add(p.id)
                yield SourceUser(id=p.id, profile=p)
            cursor = data.get("next_cursor") or ""
            if not data.get("has_next_page") or cursor in ("", "0"):
                break

    async def get_users(self, ids: list[str]) -> list[UserProfile]:
        out: list[UserProfile] = []
        # 100+ per call is the cheap tier; keep chunks at 100.
        for i in range(0, len(ids), 100):
            chunk = ids[i : i + 100]
            data = await self._get("/twitter/user/batch_info_by_ids", {"userIds": ",".join(chunk)})
            for u in data.get("users") or []:
                if u.get("unavailable"):
                    out.append(UserProfile(id=str(u["id"]), raw=u))
                    continue
                out.append(profile_from_camel(u))
        return out

    async def get_user_by_handle(self, handle: str) -> UserProfile | None:
        try:
            data = await self._get("/twitter/user/info", {"userName": handle.lstrip("@")})
        except SourceError as exc:
            if "not found" in str(exc).lower():
                return None
            raise
        u = data.get("data")
        return profile_from_camel(u) if u else None

    async def get_user_tweets(
        self, user_id: str, handle: str | None, limit: int, include_replies: bool
    ) -> list[TweetData]:
        params: dict[str, Any] = {"includeReplies": "true" if include_replies else "false"}
        if user_id:
            params["userId"] = user_id
        elif handle:
            params["userName"] = handle
        out: list[TweetData] = []
        cursor = ""
        for _ in range(10):  # hard cap on pages
            data = await self._get("/twitter/user/last_tweets", {**params, "cursor": cursor})
            tweets = (data.get("data") or {}).get("tweets") or []
            for t in tweets:
                out.append(tweet_from_api(t))
                if len(out) >= limit:
                    return out
            cursor = data.get("next_cursor") or ""
            if not tweets or not data.get("has_next_page") or cursor in ("", "0"):
                break
        return out
