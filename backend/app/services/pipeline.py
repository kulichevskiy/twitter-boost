"""Networking pipeline: stages and the automatic transitions driven by events.

candidate -> followed -> engaged -> followed_back
                     +-> no_response (deadline passed) -> unfollowed
Any stage can be set to ignored by hand. `lost` = they unfollowed me after
a mutual relationship.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Contact, Event, Person, utcnow
from ..schemas import STAGES
from .settings import Effective

WAITING = ("followed", "engaged")


def ensure_contact(session: Session, person: Person, stage: str = "candidate") -> Contact:
    c = person.contact or session.get(Contact, person.id)
    if c is None:
        c = Contact(person_id=person.id, stage=stage)
        session.add(c)
        person.contact = c
        session.flush()
    return c


def set_stage(
    session: Session,
    person: Person,
    stage: str,
    eff: Effective,
    *,
    note: str | None = None,
    at: datetime | None = None,
    source: str = "manual",
    emit_event: bool = True,
) -> Contact:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage}")
    now = at or utcnow()
    c = ensure_contact(session, person)  # new contacts start as candidate, then transition
    old = c.stage
    c.stage = stage
    if note is not None:
        c.note = note
    if stage == "followed":
        c.followed_at = c.followed_at or now
        c.deadline_at = c.followed_at + timedelta(days=eff.followback_deadline_days)
        c.closed_at = None
    elif stage == "engaged":
        c.followed_at = c.followed_at or now
        c.engaged_at = c.engaged_at or now
        c.deadline_at = c.deadline_at or now + timedelta(days=eff.followback_deadline_days)
        c.closed_at = None
    elif stage == "followed_back":
        c.followed_back_at = c.followed_back_at or now
        c.closed_at = None
    elif stage in ("unfollowed", "lost", "ignored"):
        c.closed_at = now
    elif stage == "candidate":
        c.closed_at = None
    if emit_event and old != stage:
        ev = Event(person_id=person.id, type="stage_changed", at=now, payload={"from": old, "to": stage, "source": source})
        session.add(ev)
        person.last_event_at = now
    return c


def apply_event(session: Session, person: Person, event_type: str, eff: Effective, at: datetime) -> None:
    """React to a relation event produced by sync."""
    c = person.contact or session.get(Contact, person.id)
    if event_type == "i_followed":
        if c is None or c.stage in ("candidate", "unfollowed", "no_response", "ignored"):
            # If they already follow me, this is instantly mutual.
            target = "followed_back" if person.is_follower else "followed"
            set_stage(session, person, target, eff, at=at, source="sync")
    elif event_type == "followed_me":
        if c is not None and c.stage in WAITING + ("no_response",):
            set_stage(session, person, "followed_back", eff, at=at, source="sync")
    elif event_type == "i_unfollowed":
        if c is not None and c.stage not in ("ignored",):
            set_stage(session, person, "unfollowed", eff, at=at, source="sync")
    elif event_type == "unfollowed_me":
        if c is not None and c.stage == "followed_back":
            set_stage(session, person, "lost", eff, at=at, source="sync")


def mark_overdue(session: Session, eff: Effective, now: datetime | None = None) -> int:
    """followed/engaged contacts past their deadline -> no_response."""
    now = now or utcnow()
    rows = session.execute(
        select(Contact).where(Contact.stage.in_(WAITING), Contact.deadline_at.is_not(None), Contact.deadline_at < now)
    ).scalars().all()
    n = 0
    for c in rows:
        person = session.get(Person, c.person_id)
        if person is None:
            continue
        if person.is_follower:
            set_stage(session, person, "followed_back", eff, at=now, source="sync")
        else:
            set_stage(session, person, "no_response", eff, at=now, source="sync")
        n += 1
    return n
