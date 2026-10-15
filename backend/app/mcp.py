"""MCP server for agents: thin wrappers over the same service functions.

Mounted by main.py at /mcp (streamable HTTP). Protected by the same bearer
token as the REST API (CRM_API_TOKEN) when one is set.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from .config import settings as env
from .db import session_scope
from .jobs import queue
from .models import Event, Job, Person, Sync
from .schemas import PeopleFilter
from .services import people as people_svc
from .services import pipeline
from .services.people import event_out
from .services.settings import load_effective
from .services.sync import next_sync_at


def _auth():
    if not env.crm_api_token:
        return None
    from fastmcp.server.auth import StaticTokenVerifier

    return StaticTokenVerifier(tokens={env.crm_api_token: {"client_id": "crm-agent", "scopes": ["crm"]}})


mcp = FastMCP(
    name="twitter-crm",
    instructions=(
        "CRM over my X (Twitter) account. People are followers / accounts I follow. "
        "Events record who followed or unfollowed whom and when. Contacts move through a "
        "networking pipeline: candidate -> followed -> engaged -> followed_back | no_response -> unfollowed. "
        "Tweet fetching and Claude analysis are explicit, paid actions: enqueue them only when asked."
    ),
    auth=_auth(),
)


def _dump(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


@mcp.tool
def search_people(filter: PeopleFilter) -> dict[str, Any]:
    """Search people with the shared PeopleFilter (relation, stage, tags, followers range,
    analysis score, event type/since, free-text q, sort, pagination)."""
    with session_scope() as session:
        return _dump(people_svc.search(session, filter))


@mcp.tool
def get_person(person_id: str) -> dict[str, Any]:
    """Full card: profile, contact stage, relations, notes, recent events, stored tweets, latest analysis."""
    with session_scope() as session:
        p = people_svc.get_person(session, person_id)
        if p is None:
            raise ValueError("person not found")
        return _dump(people_svc.detail(session, p))


@mcp.tool
def find_by_handle(handle: str) -> dict[str, Any] | None:
    """Look a stored person up by @handle (no network call)."""
    with session_scope() as session:
        p = people_svc.search(session, PeopleFilter(q=handle.lstrip("@"), page_size=5))
        for item in p.items:
            if (item.handle or "").lower() == handle.lstrip("@").lower():
                return _dump(item)
        return None


@mcp.tool
def list_events(since: datetime | None = None, type: str | None = None, person_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Follow/unfollow/profile/stage events, newest first. `type` may be comma-separated."""
    from sqlalchemy import select

    with session_scope() as session:
        stmt = select(Event, Person).join(Person, Person.id == Event.person_id).order_by(Event.at.desc()).limit(min(limit, 1000))
        if since:
            stmt = stmt.where(Event.at >= since)
        if type:
            stmt = stmt.where(Event.type.in_(type.split(",")))
        if person_id:
            stmt = stmt.where(Event.person_id == person_id)
        return [_dump(event_out(e, p)) for e, p in session.execute(stmt).all()]


@mcp.tool
def get_pipeline() -> dict[str, Any]:
    """Contacts grouped by stage, with overdue flags (waited longer than the follow-back deadline)."""

    from .models import Contact

    with session_scope() as session:
        rows = session.execute(people_svc.base_query().where(Contact.person_id.is_not(None))).scalars().unique().all()
        out: dict[str, list[dict[str, Any]]] = {}
        for p in rows:
            out.setdefault(p.contact.stage, []).append(_dump(people_svc.person_out(p)))
        return {"columns": out, "counts": {k: len(v) for k, v in out.items()}}


@mcp.tool
def set_stage(person_id: str, stage: str, note: str | None = None) -> dict[str, Any]:
    """Move a contact to a pipeline stage: candidate, followed, engaged, followed_back, no_response, unfollowed, lost, ignored."""
    with session_scope() as session:
        p = session.get(Person, person_id)
        if p is None:
            raise ValueError("person not found")
        eff = load_effective(session)
        c = pipeline.set_stage(session, p, stage, eff, note=note, source="mcp")
        session.flush()
        return _dump(people_svc.contact_out(c))


@mcp.tool
def add_note(person_id: str, text: str) -> dict[str, Any]:
    """Attach a free-text note to a person."""
    from .models import Note, utcnow

    with session_scope() as session:
        p = session.get(Person, person_id)
        if p is None:
            raise ValueError("person not found")
        n = Note(person_id=p.id, text=text)
        session.add(n)
        now = utcnow()
        session.add(Event(person_id=p.id, type="note_added", at=now, payload={"preview": text[:140]}))
        p.last_event_at = now
        session.flush()
        return {"id": n.id, "text": n.text, "created_at": n.created_at.isoformat()}


@mcp.tool
def tag_person(person_id: str, tag: str, remove: bool = False) -> list[str]:
    """Add (or remove) a tag on a person. Returns the person's tags."""
    from sqlalchemy import select

    from .models import PersonTag, Tag

    with session_scope() as session:
        p = people_svc.get_person(session, person_id)
        if p is None:
            raise ValueError("person not found")
        t = session.execute(select(Tag).where(Tag.name == tag)).scalar_one_or_none()
        if remove:
            if t is not None:
                link = session.get(PersonTag, (p.id, t.id))
                if link is not None:
                    session.delete(link)
        else:
            if t is None:
                t = Tag(name=tag)
                session.add(t)
                session.flush()
            if session.get(PersonTag, (p.id, t.id)) is None:
                session.add(PersonTag(person_id=p.id, tag_id=t.id))
        session.flush()
        session.refresh(p)
        return [x.name for x in p.tags]


@mcp.tool
def lookup_handle(handle: str, stage: str = "candidate") -> dict[str, Any]:
    """Fetch a profile from the data source by @handle and add it to the CRM (paid call). Returns the queued job."""
    with session_scope() as session:
        job = queue.enqueue(session, "lookup", {"handle": handle.lstrip("@"), "stage": stage}, priority=3, max_attempts=1)
        return {"job_id": job.id, "status": job.status}


@mcp.tool
def fetch_tweets(person_id: str) -> dict[str, Any]:
    """Queue a refresh of a person's recent tweets from the data source (paid call)."""
    with session_scope() as session:
        job = queue.enqueue(session, "fetch_tweets", {"person_id": person_id}, priority=3)
        return {"job_id": job.id, "status": job.status}


@mcp.tool
def analyze(person_id: str, force: bool = False, refresh_tweets: bool = False) -> dict[str, Any]:
    """Queue a Claude analysis of a person (fetches tweets first if none are stored). Paid call."""
    with session_scope() as session:
        job = queue.enqueue(
            session, "fetch_and_analyze" if refresh_tweets else "analyze", {"person_id": person_id, "force": force}, priority=3
        )
        return {"job_id": job.id, "status": job.status}


@mcp.tool
def bulk_action(action: str, filter: PeopleFilter | None = None, ids: list[str] | None = None, stage: str | None = None, tag: str | None = None, limit: int = 200) -> dict[str, Any]:
    """Apply an action to many people: fetch_tweets | analyze | fetch_and_analyze | set_stage | add_tag | remove_tag | refresh_profiles."""
    payload: dict[str, Any] = {"action": action, "limit": limit}
    if filter is not None:
        payload["filter"] = filter.model_dump(mode="json", exclude_none=True)
    if ids:
        payload["ids"] = ids
    if stage:
        payload["stage"] = stage
    if tag:
        payload["tag"] = tag
    with session_scope() as session:
        job = queue.enqueue(session, "bulk", payload, priority=2, max_attempts=1)
        return {"job_id": job.id, "status": job.status}


@mcp.tool
def run_sync() -> dict[str, Any]:
    """Queue a full snapshot sync of my followers and following lists now."""
    with session_scope() as session:
        job = queue.enqueue(session, "sync_full", {"trigger": "mcp"}, priority=10, max_attempts=1)
        return {"job_id": job.id, "status": job.status}


@mcp.tool
def get_job(job_id: int) -> dict[str, Any]:
    """Status and result of a queued job."""
    with session_scope() as session:
        j = session.get(Job, job_id)
        if j is None:
            raise ValueError("job not found")
        return {
            "id": j.id, "type": j.type, "status": j.status, "attempts": j.attempts,
            "result": j.result, "error": j.error, "payload": j.payload,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        }


@mcp.tool
def sync_status() -> dict[str, Any]:
    """Last sync summary, next scheduled sync and queue counts."""
    from sqlalchemy import select

    with session_scope() as session:
        eff = load_effective(session)
        last = session.execute(select(Sync).order_by(Sync.id.desc()).limit(1)).scalar_one_or_none()
        nxt = next_sync_at(session, eff)
        return {
            "last_sync": None if last is None else {
                "id": last.id, "status": last.status, "started_at": last.started_at.isoformat(),
                "followers": last.followers_total, "following": last.following_total,
                "added_followers": last.added_followers, "removed_followers": last.removed_followers,
                "added_following": last.added_following, "removed_following": last.removed_following,
                "error": last.error,
            },
            "next_sync_at": nxt.isoformat() if nxt else None,
            "jobs": queue.counts(session),
        }
