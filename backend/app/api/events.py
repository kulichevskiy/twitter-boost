from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, Person
from ..schemas import EventOut
from ..services.people import event_out
from .deps import DB

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def list_events(
    since: datetime | None = None,
    type: str | None = None,
    person_id: str | None = None,
    limit: int = 100,
    before_id: int | None = None,
    session: Session = DB,
):
    stmt = select(Event, Person).join(Person, Person.id == Event.person_id).order_by(Event.at.desc(), Event.id.desc())
    if since:
        stmt = stmt.where(Event.at >= since)
    if type:
        stmt = stmt.where(Event.type.in_(type.split(",")))
    if person_id:
        stmt = stmt.where(Event.person_id == person_id)
    if before_id:
        stmt = stmt.where(Event.id < before_id)
    rows = session.execute(stmt.limit(min(limit, 1000))).all()
    return [event_out(e, p) for e, p in rows]
