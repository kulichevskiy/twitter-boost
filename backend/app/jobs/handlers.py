"""Job type -> coroutine. Each handler gets the job payload and the effective settings."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic
from sqlalchemy import select

from ..db import session_scope
from ..models import Person, PersonTag, Tag
from ..schemas import PeopleFilter
from ..services import analysis as analysis_svc
from ..services import people as people_svc
from ..services import pipeline
from ..services import sync as sync_svc
from ..services import tweets as tweets_svc
from ..services.llm import LLMError  # noqa: F401 - retryable, listed for clarity
from ..services.settings import Effective
from ..sources.registry import open_sources
from ..sources.types import NotConfigured, OutOfCredits
from . import queue

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any], Effective], Awaitable[dict[str, Any]]]

NON_RETRYABLE = (
    OutOfCredits,
    NotConfigured,
    ValueError,
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.BadRequestError,
    anthropic.NotFoundError,
)


async def sync_full(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    sync_id = await sync_svc.run_sync(eff, trigger=payload.get("trigger", "job"))
    with session_scope() as session:
        from ..models import Sync

        s = session.get(Sync, sync_id)
        return {
            "sync_id": sync_id,
            "status": s.status,
            "followers": s.followers_total,
            "following": s.following_total,
            "added_followers": s.added_followers,
            "removed_followers": s.removed_followers,
            "added_following": s.added_following,
            "removed_following": s.removed_following,
            "error": s.error,
        }


async def fetch_tweets(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    pid = payload["person_id"]
    limit = int(payload.get("limit") or eff.analysis_tweets)
    include_replies = bool(payload.get("include_replies", eff.analysis_include_replies))
    async with open_sources(eff, ["tweets"]) as (src, counter):
        with session_scope() as session:
            person = session.get(Person, pid)
            if person is None:
                raise ValueError(f"person {pid} not found")
            n = await tweets_svc.refresh_tweets(session, src["tweets"], person, limit, include_replies)
            return {"person_id": pid, "new_tweets": n, "requests": counter.requests}


async def analyze(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    pid = payload["person_id"]
    force = bool(payload.get("force", False))
    with session_scope() as session:
        person = session.get(Person, pid)
        if person is None:
            raise ValueError(f"person {pid} not found")
        if person.tweets_fetched_at is None and payload.get("fetch_if_missing", True):
            async with open_sources(eff, ["tweets"]) as (src, _counter):
                await tweets_svc.refresh_tweets(
                    session, src["tweets"], person, eff.analysis_tweets, eff.analysis_include_replies
                )
        a, created = await analysis_svc.analyze_person(session, eff, person, force=force)
        return {"person_id": pid, "analysis_id": a.id, "created": created, "score": a.result.get("relevance_score")}


async def fetch_and_analyze(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    r1 = await fetch_tweets(payload, eff)
    r2 = await analyze({**payload, "fetch_if_missing": False}, eff)
    return {**r1, **r2}


async def refresh_profiles(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    ids: list[str] = payload["person_ids"]
    async with open_sources(eff, ["profiles"]) as (src, counter):
        profiles = await src["profiles"].get_users(ids)
    with session_scope() as session:
        for prof in profiles:
            people_svc.upsert_profile(session, prof)
    return {"requested": len(ids), "refreshed": len(profiles), "requests": counter.requests}


async def lookup(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    """Add a person by handle (someone I plan to follow)."""
    handle = payload["handle"].lstrip("@")
    stage = payload.get("stage") or "candidate"
    async with open_sources(eff, ["profiles"]) as (src, _c):
        prof = await src["profiles"].get_user_by_handle(handle)
    if prof is None:
        raise ValueError(f"@{handle} not found")
    with session_scope() as session:
        person, _ = people_svc.upsert_profile(session, prof)
        pipeline.set_stage(session, person, stage, eff, source="lookup")
        return {"person_id": person.id, "handle": person.handle}


async def bulk(payload: dict[str, Any], eff: Effective) -> dict[str, Any]:
    """Fan a bulk action out into per-person jobs (or apply cheap ones inline)."""
    action = payload["action"]
    ids: list[str] = payload.get("ids") or []
    if payload.get("filter"):
        with session_scope() as session:
            ids = ids or people_svc.ids_for_filter(session, PeopleFilter.model_validate(payload["filter"]), int(payload.get("limit", 500)))
    ids = ids[: int(payload.get("limit", 500))]
    created = 0
    with session_scope() as session:
        if action in ("fetch_tweets", "analyze", "fetch_and_analyze"):
            for pid in ids:
                queue.enqueue(session, action, {"person_id": pid, "force": payload.get("force", False)}, priority=-1)
                created += 1
        elif action == "refresh_profiles":
            for i in range(0, len(ids), 100):
                queue.enqueue(session, "refresh_profiles", {"person_ids": ids[i : i + 100]}, priority=-1)
                created += 1
        elif action == "set_stage":
            for pid in ids:
                person = session.get(Person, pid)
                if person is not None:
                    pipeline.set_stage(session, person, payload["stage"], eff, source="bulk")
                    created += 1
        elif action in ("add_tag", "remove_tag"):
            name = payload["tag"]
            tag = session.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
            if tag is None and action == "add_tag":
                tag = Tag(name=name)
                session.add(tag)
                session.flush()
            for pid in ids:
                link = session.get(PersonTag, (pid, tag.id)) if tag else None
                if action == "add_tag" and link is None:
                    session.add(PersonTag(person_id=pid, tag_id=tag.id))
                    created += 1
                elif action == "remove_tag" and link is not None:
                    session.delete(link)
                    created += 1
        else:
            raise ValueError(f"unknown bulk action {action}")
    return {"action": action, "people": len(ids), "created": created}


HANDLERS: dict[str, Handler] = {
    "sync_full": sync_full,
    "fetch_tweets": fetch_tweets,
    "analyze": analyze,
    "fetch_and_analyze": fetch_and_analyze,
    "refresh_profiles": refresh_profiles,
    "lookup": lookup,
    "bulk": bulk,
}
