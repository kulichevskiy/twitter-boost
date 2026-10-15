"""Deterministic synthetic source for development and tests.

Generates a stable population and mutates it a little on every sync so the
diff/event pipeline has something to chew on without spending credits.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from .base import RequestCounter
from .types import AccountRef, SourceUser, TweetData, UserProfile

FIRST = ["Alex", "Maria", "Ivan", "Olga", "Dmitry", "Anna", "Sergey", "Nina", "Pavel", "Lena", "Max", "Kate"]
ROLES = ["founder", "indie hacker", "VC", "growth marketer", "iOS dev", "designer", "CTO", "angel", "PM"]
TOPICS = ["AI", "SaaS", "mobile", "fintech", "web3", "no-code", "B2B sales", "DTC", "devtools", "climate"]

_state: dict[str, int] = {"epoch": 0}


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha1(seed.encode()).hexdigest()[:12], 16))


def make_profile(i: int) -> UserProfile:
    r = _rng(f"user-{i}")
    first = r.choice(FIRST)
    role = r.choice(ROLES)
    topics = r.sample(TOPICS, 2)
    handle = f"{first.lower()}_{role.split()[0].lower()}{i}"
    return UserProfile(
        id=str(100000 + i),
        handle=handle,
        name=f"{first} {role.title()}",
        bio=f"{role.title()} building in {topics[0]} and {topics[1]}. Tweets about {topics[0].lower()}.",
        location=r.choice(["Berlin", "Lisbon", "SF", "London", "Remote", ""]) or None,
        url=f"https://example.com/{handle}" if r.random() > 0.5 else None,
        avatar_url=None,
        followers_count=int(r.lognormvariate(6, 1.5)),
        following_count=int(r.lognormvariate(5.5, 1)),
        tweets_count=int(r.lognormvariate(6.5, 1.2)),
        verified=r.random() > 0.8,
        protected=False,
        created_at=datetime(2015, 1, 1) + timedelta(days=r.randint(0, 3500)),
        raw={"fake": True},
    )


class FakeSource:
    name = "fake"

    def __init__(self, counter: RequestCounter | None = None, followers: int = 120, following: int = 90) -> None:
        self.counter = counter or RequestCounter()
        self.n_followers = followers
        self.n_following = following

    async def aclose(self) -> None:
        return None

    def bump(self) -> None:
        """Advance the synthetic world one step (called between syncs in tests)."""
        _state["epoch"] += 1

    def _followers_ids(self) -> list[int]:
        e = _state["epoch"]
        base = list(range(self.n_followers))
        # every epoch: lose 2 followers, gain 3 new ones
        lost = set(range(min(2 * e, self.n_followers // 2)))
        gained = list(range(self.n_followers + 1000, self.n_followers + 1000 + 3 * e))
        return [i for i in base if i not in lost] + gained

    def _following_ids(self) -> list[int]:
        e = _state["epoch"]
        base = list(range(50, 50 + self.n_following))  # overlap with followers = mutuals
        gained = list(range(5000, 5000 + 2 * e))
        return base + gained

    async def me(self, ref: AccountRef) -> UserProfile:
        self.counter.requests += 1
        return UserProfile(
            id=ref.id or "1",
            handle=ref.handle or "me",
            name="Me",
            followers_count=len(self._followers_ids()),
            following_count=len(self._following_ids()),
            raw={"fake": True},
        )

    async def iter_followers(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        self.counter.requests += 1
        for i in self._followers_ids():
            yield SourceUser(id=str(100000 + i))

    async def iter_following(self, ref: AccountRef) -> AsyncIterator[SourceUser]:
        self.counter.requests += 1
        for i in self._following_ids():
            p = make_profile(i)
            yield SourceUser(id=p.id, profile=p)

    async def get_users(self, ids: list[str]) -> list[UserProfile]:
        self.counter.requests += max(1, len(ids) // 100)
        return [make_profile(int(i) - 100000) for i in ids]

    async def get_user_by_handle(self, handle: str) -> UserProfile | None:
        self.counter.requests += 1
        r = _rng(handle)
        p = make_profile(r.randint(20000, 29999))
        p.handle = handle.lstrip("@")
        return p

    async def get_user_tweets(
        self, user_id: str, handle: str | None, limit: int, include_replies: bool
    ) -> list[TweetData]:
        self.counter.requests += 1
        r = _rng(f"tweets-{user_id}")
        p = make_profile(int(user_id) - 100000)
        out = []
        for k in range(min(limit, 30)):
            topic = r.choice(TOPICS)
            out.append(
                TweetData(
                    id=f"{user_id}{k:03d}",
                    text=r.choice(
                        [
                            f"Shipped a new {topic} feature today. Lessons learned in thread 🧵",
                            f"Hot take: most {topic} startups fail at distribution, not product.",
                            f"Looking for beta users for our {topic} tool. DM me!",
                            f"Week {k}: MRR update and what we changed in {topic} onboarding.",
                        ]
                    ),
                    created_at=datetime.now() - timedelta(days=k * 2, hours=r.randint(0, 23)),
                    lang="en",
                    is_reply=False,
                    url=f"https://x.com/{p.handle}/status/{user_id}{k:03d}",
                    metrics={"likes": r.randint(0, 200), "retweets": r.randint(0, 20), "replies": r.randint(0, 30), "views": r.randint(100, 20000)},
                    raw={"fake": True},
                )
            )
        return out
