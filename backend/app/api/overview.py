from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..jobs import queue
from ..models import Account, Contact, Event, Person, Sync, utcnow
from ..schemas import AccountOut, OverviewOut, PipelineOut
from ..services.people import WAITING_STAGES, base_query, event_out, person_out
from ..services.settings import Effective
from ..services.sync import next_sync_at
from .deps import DB, EFF
from .syncs import sync_out

router = APIRouter(tags=["overview"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/overview", response_model=OverviewOut)
def overview(session: Session = DB, eff: Effective = EFF):
    now = utcnow()
    acc = session.get(Account, 1)
    followers = session.execute(select(func.count()).where(Person.is_follower.is_(True))).scalar_one()
    following = session.execute(select(func.count()).where(Person.is_following.is_(True))).scalar_one()
    mutual = session.execute(
        select(func.count()).where(Person.is_follower.is_(True), Person.is_following.is_(True))
    ).scalar_one()
    waiting = session.execute(select(func.count()).where(Contact.stage.in_(WAITING_STAGES))).scalar_one()
    overdue = session.execute(
        select(func.count()).where(Contact.stage.in_(WAITING_STAGES), Contact.deadline_at < now)
    ).scalar_one()
    deltas = {}
    for label, days in (("7d", 7), ("30d", 30)):
        since = now - timedelta(days=days)
        rows = session.execute(
            select(Event.type, func.count()).where(Event.at >= since).group_by(Event.type)
        ).all()
        deltas[label] = {t: n for t, n in rows}
    last_sync = session.execute(select(Sync).order_by(Sync.id.desc()).limit(1)).scalar_one_or_none()
    recent = session.execute(
        select(Event, Person).join(Person, Person.id == Event.person_id).order_by(Event.at.desc(), Event.id.desc()).limit(20)
    ).all()
    stages = {s: n for s, n in session.execute(select(Contact.stage, func.count()).group_by(Contact.stage)).all()}
    return OverviewOut(
        account=AccountOut.model_validate(acc, from_attributes=True) if acc else None,
        followers=followers,
        following=following,
        mutual=mutual,
        not_following_back=following - mutual,
        fans=followers - mutual,
        waiting=waiting,
        overdue=overdue,
        deltas=deltas,
        last_sync=sync_out(last_sync) if last_sync else None,
        next_sync_at=next_sync_at(session, eff, now),
        jobs=queue.counts(session),
        recent_events=[event_out(e, p) for e, p in recent],
        stages=stages,
    )


@router.get("/pipeline", response_model=PipelineOut)
def pipeline_board(session: Session = DB):
    now = utcnow()
    rows = (
        session.execute(
            base_query().where(Contact.person_id.is_not(None)).order_by(Contact.deadline_at.asc().nulls_last(), Contact.updated_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    columns: dict[str, list] = {}
    for p in rows:
        columns.setdefault(p.contact.stage, []).append(person_out(p, now))
    return PipelineOut(columns=columns, counts={k: len(v) for k, v in columns.items()})
