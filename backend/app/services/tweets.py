from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Person, Tweet, utcnow
from ..sources.base import Source
from ..sources.types import TweetData


def store_tweets(session: Session, person: Person, tweets: list[TweetData], now: datetime | None = None) -> int:
    now = now or utcnow()
    n = 0
    newest: datetime | None = person.last_tweet_at
    for t in tweets:
        row = session.get(Tweet, t.id)
        if row is None:
            row = Tweet(id=t.id, person_id=person.id, text=t.text)
            session.add(row)
            n += 1
        row.text = t.text
        row.created_at = t.created_at
        row.lang = t.lang
        row.is_reply = t.is_reply
        row.is_retweet = t.is_retweet
        row.is_quote = t.is_quote
        row.url = t.url
        row.metrics = t.metrics
        row.raw = t.raw
        row.fetched_at = now
        if t.created_at and (newest is None or t.created_at > newest):
            newest = t.created_at
    person.last_tweet_at = newest
    person.tweets_fetched_at = now
    session.flush()
    return n


async def refresh_tweets(session: Session, source: Source, person: Person, limit: int, include_replies: bool) -> int:
    tweets = await source.get_user_tweets(person.id, person.handle, limit, include_replies)
    return store_tweets(session, person, tweets)
