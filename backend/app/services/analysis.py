"""Profile + recent tweets -> structured verdict from Claude.

Cached by hash of (prompt version, model, bio, tweet ids): re-running on
unchanged input is free.
"""

from __future__ import annotations

import hashlib
import json
import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Analysis, Event, Person, Tweet, utcnow
from ..schemas import AnalysisResult
from .settings import Effective

log = logging.getLogger(__name__)

PROMPT_VERSION = "2"

SYSTEM = """You help a founder run a CRM for their X (Twitter) account.
You are given a person's profile and their recent tweets. Work out who they are,
what they post about and how useful they are for networking given the user's goal.

Rules:
- Write summary, relevance_reasons and red_flags in English, short and concrete.
- Write opener in the language the person tweets in: it is a draft first comment
  under one of their tweets, hooked to a specific topic from their tweets, no
  flattery, no selling.
- Score 5: direct match with the goal (active founder/investor/operator from the
  same scene, live account, replies to people). 3: adjacent, or a half-dead
  account. 1: bot, spam, course seller, empty account, irrelevant topic.
- If there are no tweets or only retweets, say so in summary and score at most 2,
  unless the bio alone is highly relevant.
- Do not invent facts that are not in the data."""


def _profile_block(p: Person) -> str:
    lines = [
        f"@{p.handle}" if p.handle else f"id {p.id}",
        f"Name: {p.name or '—'}",
        f"Bio: {p.bio or '—'}",
        f"Location: {p.location or '—'}",
        f"Website: {p.url or '—'}",
        f"Followers: {p.followers_count if p.followers_count is not None else '—'}, "
        f"following: {p.following_count if p.following_count is not None else '—'}, "
        f"tweets: {p.tweets_count if p.tweets_count is not None else '—'}",
        f"Account created: {p.account_created_at.date().isoformat() if p.account_created_at else '—'}",
        f"Verified: {'yes' if p.verified else 'no'}",
        f"Relationship with me: {'follows me' if p.is_follower else 'does not follow me'}, "
        f"{'I follow them' if p.is_following else 'I do not follow them'}",
    ]
    return "\n".join(lines)


def _tweets_block(tweets: list[Tweet]) -> str:
    if not tweets:
        return "(no tweets)"
    out = []
    for t in tweets:
        when = t.created_at.date().isoformat() if t.created_at else "?"
        kind = "reply" if t.is_reply else ("quote" if t.is_quote else "tweet")
        m = t.metrics or {}
        stats = f"❤{m.get('likes', 0)} 🔁{m.get('retweets', 0)} 💬{m.get('replies', 0)} 👁{m.get('views', 0)}"
        out.append(f"[{when} {kind} {stats}] {t.text.strip()}")
    return "\n".join(out)


def select_tweets(session: Session, person: Person, limit: int, include_replies: bool) -> list[Tweet]:
    stmt = select(Tweet).where(Tweet.person_id == person.id, Tweet.is_retweet.is_(False))
    if not include_replies:
        stmt = stmt.where(Tweet.is_reply.is_(False))
    stmt = stmt.order_by(Tweet.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def input_hash(eff: Effective, person: Person, tweets: list[Tweet]) -> str:
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(f"{eff.analysis_provider}:{eff.analysis_model}".encode())
    h.update((eff.analysis_goal or "").encode())
    h.update((person.bio or "").encode())
    h.update((person.name or "").encode())
    for t in tweets:
        h.update(t.id.encode())
    return h.hexdigest()


def latest_analysis(session: Session, person_id: str) -> Analysis | None:
    return session.execute(
        select(Analysis).where(Analysis.person_id == person_id).order_by(Analysis.created_at.desc()).limit(1)
    ).scalar_one_or_none()


async def analyze_person(session: Session, eff: Effective, person: Person, force: bool = False) -> tuple[Analysis, bool]:
    """Returns (analysis, created). created=False means the cache was hit."""
    from . import llm

    tweets = select_tweets(session, person, eff.analysis_tweets, eff.analysis_include_replies)
    digest = input_hash(eff, person, tweets)
    if not force:
        cached = session.execute(
            select(Analysis).where(Analysis.person_id == person.id, Analysis.input_hash == digest).limit(1)
        ).scalar_one_or_none()
        if cached is not None:
            return cached, False

    user_msg = (
        f"User's goal:\n{eff.analysis_goal}\n\n"
        f"Profile:\n{_profile_block(person)}\n\n"
        f"Recent tweets ({len(tweets)}):\n{_tweets_block(tweets)}\n\n"
        "Answer strictly as JSON matching the given schema."
    )
    schema = AnalysisResult.model_json_schema()
    schema["additionalProperties"] = False
    raw, meta = await llm.complete_json(eff, SYSTEM, user_msg, schema)
    try:
        result = AnalysisResult.model_validate(raw)
    except ValidationError as exc:
        raise llm.LLMError(f"model output failed schema validation: {exc.errors()[:3]}") from exc

    now = utcnow()
    analysis = Analysis(
        person_id=person.id,
        created_at=now,
        model=f"{meta.get('provider')}:{meta.get('model')}"[:64],
        prompt_version=PROMPT_VERSION,
        input_hash=digest,
        tweets_used=len(tweets),
        result=json.loads(result.model_dump_json()),
        usage=meta,
    )
    session.add(analysis)
    person.relevance_score = result.relevance_score
    person.persona = result.persona
    person.primary_language = result.language
    person.analyzed_at = now
    person.last_event_at = now
    session.add(Event(person_id=person.id, type="analyzed", at=now, payload={"score": result.relevance_score, "persona": result.persona}))
    session.flush()
    return analysis, True
