from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs import queue
from ..models import Event, Note, Person, PersonTag, Tag, utcnow
from ..schemas import (
    BulkAction,
    ContactOut,
    ContactPatch,
    JobOut,
    LookupIn,
    NoteIn,
    NoteOut,
    Paginated,
    PeopleFilter,
    PersonDetail,
    PersonOut,
    TagIn,
    TagOut,
)
from ..services import people as svc
from ..services import pipeline
from ..services.settings import Effective
from .deps import DB, EFF
from .jobs import job_out

router = APIRouter(prefix="/people", tags=["people"])


def filter_dep(
    q: str | None = None,
    relation: str = "any",
    stage: Annotated[list[str] | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    followers_min: int | None = None,
    followers_max: int | None = None,
    verified: bool | None = None,
    has_analysis: bool | None = None,
    score_min: int | None = None,
    persona: Annotated[list[str] | None, Query()] = None,
    language: str | None = None,
    event_type: str | None = None,
    event_since: str | None = None,
    first_seen_after: str | None = None,
    last_tweet_after: str | None = None,
    overdue: bool | None = None,
    sort: str = "-last_event",
    page: int = 1,
    page_size: int = 50,
) -> PeopleFilter:
    try:
        return PeopleFilter.model_validate(
            {
                "q": q,
                "relation": relation,
                "stage": stage or None,
                "tags": tags or None,
                "followers_min": followers_min,
                "followers_max": followers_max,
                "verified": verified,
                "has_analysis": has_analysis,
                "score_min": score_min,
                "persona": persona or None,
                "language": language,
                "event_type": event_type,
                "event_since": event_since,
                "first_seen_after": first_seen_after,
                "last_tweet_after": last_tweet_after,
                "overdue": overdue,
                "sort": sort,
                "page": page,
                "page_size": page_size,
            }
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("", response_model=Paginated[PersonOut])
def list_people(f: PeopleFilter = Depends(filter_dep), session: Session = DB):
    return svc.search(session, f)


@router.post("/search", response_model=Paginated[PersonOut])
def search_people(f: PeopleFilter, session: Session = DB):
    """Same as GET but takes the filter as a JSON body (handy for agents)."""
    return svc.search(session, f)


@router.post("/lookup", response_model=JobOut, status_code=202)
def lookup_person(body: LookupIn, session: Session = DB):
    job = queue.enqueue(session, "lookup", {"handle": body.handle.lstrip("@"), "stage": body.stage}, priority=3, max_attempts=1)
    session.commit()
    return job_out(job)


@router.post("/bulk", response_model=JobOut, status_code=202)
def bulk_action(body: BulkAction, session: Session = DB):
    if not body.ids and body.filter is None:
        raise HTTPException(422, "ids or filter required")
    if body.action == "set_stage" and not body.stage:
        raise HTTPException(422, "stage required")
    if body.action in ("add_tag", "remove_tag") and not body.tag:
        raise HTTPException(422, "tag required")
    payload = body.model_dump(mode="json", exclude_none=True)
    job = queue.enqueue(session, "bulk", payload, priority=2, max_attempts=1)
    session.commit()
    return job_out(job)


def _get(session: Session, person_id: str) -> Person:
    p = svc.get_person(session, person_id)
    if p is None:
        raise HTTPException(404, "person not found")
    return p


@router.get("/{person_id}", response_model=PersonDetail)
def person_detail(person_id: str, session: Session = DB):
    return svc.detail(session, _get(session, person_id))


@router.patch("/{person_id}/contact", response_model=ContactOut)
def patch_contact(person_id: str, body: ContactPatch, session: Session = DB, eff: Effective = EFF):
    p = _get(session, person_id)
    if body.stage:
        c = pipeline.set_stage(session, p, body.stage, eff, note=body.note)
    else:
        c = pipeline.ensure_contact(session, p)
        if body.note is not None:
            c.note = body.note
    if body.deadline_at is not None:
        c.deadline_at = body.deadline_at
    if body.followed_at is not None:
        c.followed_at = body.followed_at
    if body.engaged_at is not None:
        c.engaged_at = body.engaged_at
    session.commit()
    session.refresh(c)
    return svc.contact_out(c)


@router.post("/{person_id}/notes", response_model=NoteOut, status_code=201)
def add_note(person_id: str, body: NoteIn, session: Session = DB):
    p = _get(session, person_id)
    note = Note(person_id=p.id, text=body.text)
    session.add(note)
    now = utcnow()
    session.add(Event(person_id=p.id, type="note_added", at=now, payload={"preview": body.text[:140]}))
    p.last_event_at = now
    session.commit()
    return NoteOut(id=note.id, text=note.text, created_at=note.created_at)


@router.delete("/{person_id}/notes/{note_id}", status_code=204)
def delete_note(person_id: str, note_id: int, session: Session = DB):
    note = session.get(Note, note_id)
    if note is None or note.person_id != person_id:
        raise HTTPException(404, "note not found")
    session.delete(note)
    session.commit()


@router.post("/{person_id}/tags", response_model=list[TagOut])
def add_tag(person_id: str, body: TagIn, session: Session = DB):
    p = _get(session, person_id)
    tag = session.execute(select(Tag).where(Tag.name == body.name)).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=body.name, color=body.color)
        session.add(tag)
        session.flush()
    if session.get(PersonTag, (p.id, tag.id)) is None:
        session.add(PersonTag(person_id=p.id, tag_id=tag.id))
    session.commit()
    session.refresh(p)
    return [TagOut(id=t.id, name=t.name, color=t.color) for t in p.tags]


@router.delete("/{person_id}/tags/{tag_name}", response_model=list[TagOut])
def remove_tag(person_id: str, tag_name: str, session: Session = DB):
    p = _get(session, person_id)
    tag = session.execute(select(Tag).where(Tag.name == tag_name)).scalar_one_or_none()
    if tag is not None:
        link = session.get(PersonTag, (p.id, tag.id))
        if link is not None:
            session.delete(link)
    session.commit()
    session.refresh(p)
    return [TagOut(id=t.id, name=t.name, color=t.color) for t in p.tags]


@router.post("/{person_id}/tweets/refresh", response_model=JobOut, status_code=202)
def refresh_tweets(person_id: str, session: Session = DB):
    _get(session, person_id)
    job = queue.enqueue(session, "fetch_tweets", {"person_id": person_id}, priority=3)
    session.commit()
    return job_out(job)


@router.post("/{person_id}/analyze", response_model=JobOut, status_code=202)
def analyze(person_id: str, force: bool = False, refresh: bool = False, session: Session = DB):
    _get(session, person_id)
    job_type = "fetch_and_analyze" if refresh else "analyze"
    job = queue.enqueue(session, job_type, {"person_id": person_id, "force": force}, priority=3)
    session.commit()
    return job_out(job)
