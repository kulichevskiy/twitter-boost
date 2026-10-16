"""PeopleFilter -> SQL, plus the Person -> DTO mapping used everywhere."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import Analysis, Contact, Event, Note, Person, PersonTag, Relation, Tag, Tweet, utcnow
from ..schemas import (
    AnalysisOut,
    AnalysisResult,
    ContactOut,
    EventOut,
    NoteOut,
    Paginated,
    PeopleFilter,
    PersonDetail,
    PersonOut,
    RelationOut,
    TagOut,
    TweetOut,
)

WAITING_STAGES = ("followed", "engaged")


def is_overdue(contact: Contact | None, now: datetime | None = None) -> bool:
    if contact is None or contact.stage not in WAITING_STAGES or contact.deadline_at is None:
        return False
    return contact.deadline_at < (now or utcnow())


def person_out(p: Person, now: datetime | None = None) -> PersonOut:
    c = p.contact
    return PersonOut(
        id=p.id,
        handle=p.handle,
        name=p.name,
        bio=p.bio,
        location=p.location,
        url=p.url,
        avatar_url=p.avatar_url,
        followers_count=p.followers_count,
        following_count=p.following_count,
        tweets_count=p.tweets_count,
        verified=p.verified,
        protected=p.protected,
        account_created_at=p.account_created_at,
        first_seen_at=p.first_seen_at,
        profile_synced_at=p.profile_synced_at,
        is_follower=p.is_follower,
        is_following=p.is_following,
        last_event_at=p.last_event_at,
        last_tweet_at=p.last_tweet_at,
        tweets_fetched_at=p.tweets_fetched_at,
        relevance_score=p.relevance_score,
        persona=p.persona,
        primary_language=p.primary_language,
        analyzed_at=p.analyzed_at,
        stage=c.stage if c else None,  # type: ignore[arg-type]
        deadline_at=c.deadline_at if c else None,
        overdue=is_overdue(c, now),
        tags=[TagOut(id=t.id, name=t.name, color=t.color) for t in p.tags],
    )


def contact_out(c: Contact, now: datetime | None = None) -> ContactOut:
    return ContactOut(
        stage=c.stage,  # type: ignore[arg-type]
        followed_at=c.followed_at,
        engaged_at=c.engaged_at,
        followed_back_at=c.followed_back_at,
        deadline_at=c.deadline_at,
        closed_at=c.closed_at,
        note=c.note,
        overdue=is_overdue(c, now),
        updated_at=c.updated_at,
    )


def event_out(e: Event, p: Person | None = None) -> EventOut:
    return EventOut(
        id=e.id,
        person_id=e.person_id,
        type=e.type,
        at=e.at,
        sync_id=e.sync_id,
        payload=e.payload,
        handle=p.handle if p else None,
        name=p.name if p else None,
        avatar_url=p.avatar_url if p else None,
    )


def tweet_out(t: Tweet) -> TweetOut:
    return TweetOut(
        id=t.id,
        text=t.text,
        created_at=t.created_at,
        lang=t.lang,
        is_reply=t.is_reply,
        is_retweet=t.is_retweet,
        is_quote=t.is_quote,
        url=t.url,
        metrics=t.metrics,
    )


def analysis_out(a: Analysis) -> AnalysisOut:
    return AnalysisOut(
        id=a.id,
        created_at=a.created_at,
        model=a.model,
        prompt_version=a.prompt_version,
        tweets_used=a.tweets_used,
        result=AnalysisResult.model_validate(a.result),
        usage=a.usage,
    )


def with_contact(stmt: Select) -> Select:
    """Every people query left-joins Contact once so filters and sorts can use it."""
    return stmt.outerjoin(Contact, Contact.person_id == Person.id)


def base_query() -> Select[tuple[Person]]:
    return with_contact(select(Person)).options(selectinload(Person.contact), selectinload(Person.tags))


def apply_filter(stmt: Select[tuple[Person]], f: PeopleFilter, now: datetime | None = None) -> Select[tuple[Person]]:
    now = now or utcnow()
    if f.q:
        like = f"%{f.q.strip().lstrip('@')}%"
        stmt = stmt.where(or_(Person.handle.ilike(like), Person.name.ilike(like), Person.bio.ilike(like)))
    rel = f.relation
    if rel == "mutual":
        stmt = stmt.where(Person.is_follower.is_(True), Person.is_following.is_(True))
    elif rel == "follower_only":
        stmt = stmt.where(Person.is_follower.is_(True), Person.is_following.is_(False))
    elif rel == "following_only":
        stmt = stmt.where(Person.is_follower.is_(False), Person.is_following.is_(True))
    elif rel == "follower":
        stmt = stmt.where(Person.is_follower.is_(True))
    elif rel == "following":
        stmt = stmt.where(Person.is_following.is_(True))
    elif rel == "none":
        stmt = stmt.where(Person.is_follower.is_(False), Person.is_following.is_(False))
    elif rel == "unfollowed_me":
        stmt = stmt.where(
            exists().where(
                and_(Relation.person_id == Person.id, Relation.direction == "follower", Relation.active.is_(False))
            )
        )
    elif rel == "i_unfollowed":
        stmt = stmt.where(
            exists().where(
                and_(Relation.person_id == Person.id, Relation.direction == "following", Relation.active.is_(False))
            )
        )
    if f.stage:
        stmt = stmt.where(Contact.stage.in_(f.stage))
    if f.overdue:
        stmt = stmt.where(Contact.stage.in_(WAITING_STAGES), Contact.deadline_at < now)
    if f.tags:
        for name in f.tags:
            stmt = stmt.where(
                exists().where(
                    and_(PersonTag.person_id == Person.id, PersonTag.tag_id == Tag.id, Tag.name == name)
                )
            )
    if f.followers_min is not None:
        stmt = stmt.where(Person.followers_count >= f.followers_min)
    if f.followers_max is not None:
        stmt = stmt.where(Person.followers_count <= f.followers_max)
    if f.verified is not None:
        stmt = stmt.where(Person.verified.is_(f.verified))
    if f.has_analysis is True:
        stmt = stmt.where(Person.analyzed_at.is_not(None))
    elif f.has_analysis is False:
        stmt = stmt.where(Person.analyzed_at.is_(None))
    if f.score_min is not None:
        stmt = stmt.where(Person.relevance_score >= f.score_min)
    if f.persona:
        stmt = stmt.where(Person.persona.in_(f.persona))
    if f.language:
        stmt = stmt.where(Person.primary_language == f.language)
    if f.event_type:
        cond = [Event.person_id == Person.id, Event.type == f.event_type]
        if f.event_since:
            cond.append(Event.at >= f.event_since)
        stmt = stmt.where(exists().where(and_(*cond)))
    if f.first_seen_after:
        stmt = stmt.where(Person.first_seen_at >= f.first_seen_after)
    if f.last_tweet_after:
        stmt = stmt.where(Person.last_tweet_at >= f.last_tweet_after)
    return stmt


def apply_sort(stmt: Select[tuple[Person]], sort: str) -> Select[tuple[Person]]:
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    col: Any
    if key == "handle":
        col = func.lower(Person.handle)
    elif key == "followers":
        col = Person.followers_count
    elif key == "tweets":
        col = Person.tweets_count
    elif key == "first_seen":
        col = Person.first_seen_at
    elif key == "score":
        col = Person.relevance_score
    elif key == "deadline":
        col = Contact.deadline_at
    else:
        col = func.coalesce(Person.last_event_at, Person.first_seen_at)
    order = col.desc() if desc else col.asc()
    return stmt.order_by(order.nulls_last(), Person.id)


def search(session: Session, f: PeopleFilter) -> Paginated[PersonOut]:
    now = utcnow()
    stmt = apply_filter(base_query(), f, now)
    total = session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    stmt = apply_sort(stmt, f.sort).offset((f.page - 1) * f.page_size).limit(f.page_size)
    rows = session.execute(stmt).scalars().unique().all()
    return Paginated(items=[person_out(p, now) for p in rows], total=total, page=f.page, page_size=f.page_size)


def ids_for_filter(session: Session, f: PeopleFilter, limit: int) -> list[str]:
    stmt = apply_filter(with_contact(select(Person.id)), f)
    stmt = apply_sort(stmt, f.sort).limit(limit)  # type: ignore[arg-type]
    return [r[0] for r in session.execute(stmt).all()]


def get_person(session: Session, person_id: str) -> Person | None:
    return session.execute(base_query().where(Person.id == person_id)).scalars().unique().one_or_none()


def detail(session: Session, p: Person) -> PersonDetail:
    now = utcnow()
    relations = session.execute(select(Relation).where(Relation.person_id == p.id)).scalars().all()
    notes = session.execute(select(Note).where(Note.person_id == p.id).order_by(Note.created_at.desc())).scalars().all()
    events = (
        session.execute(select(Event).where(Event.person_id == p.id).order_by(Event.at.desc()).limit(100)).scalars().all()
    )
    tweets = (
        session.execute(select(Tweet).where(Tweet.person_id == p.id).order_by(Tweet.created_at.desc()).limit(100))
        .scalars()
        .all()
    )
    latest = session.execute(
        select(Analysis).where(Analysis.person_id == p.id).order_by(Analysis.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    count = session.execute(select(func.count(Analysis.id)).where(Analysis.person_id == p.id)).scalar_one()
    return PersonDetail(
        person=person_out(p, now),
        contact=contact_out(p.contact, now) if p.contact else None,
        relations=[
            RelationOut(
                direction=r.direction,
                active=r.active,
                first_seen_at=r.first_seen_at,
                last_seen_at=r.last_seen_at,
                ended_at=r.ended_at,
            )
            for r in relations
        ],
        notes=[NoteOut(id=n.id, text=n.text, created_at=n.created_at) for n in notes],
        events=[event_out(e) for e in events],
        tweets=[tweet_out(t) for t in tweets],
        analysis=analysis_out(latest) if latest else None,
        analyses_count=count,
    )


def upsert_profile(session: Session, profile: Any, now: datetime | None = None) -> tuple[Person, dict[str, Any]]:
    """Create or update a Person from a sources.types.UserProfile.

    Returns the person and a dict of changed fields {field: {"old":..,"new":..}}
    (empty on create, so callers can decide whether to emit profile_changed).
    """
    now = now or utcnow()
    p = session.get(Person, profile.id)
    changes: dict[str, Any] = {}
    if p is None:
        p = Person(id=profile.id, first_seen_at=now)
        session.add(p)
        created = True
    else:
        created = False
    tracked = ("handle", "name", "bio", "location", "url")
    for field in tracked:
        new = getattr(profile, field)
        old = getattr(p, field)
        if new is not None and new != old:
            if not created and old is not None:
                changes[field] = {"old": old, "new": new}
            setattr(p, field, new)
    for field in ("avatar_url", "followers_count", "following_count", "tweets_count"):
        new = getattr(profile, field)
        if new is not None:
            setattr(p, field, new)
    p.verified = bool(profile.verified)
    p.protected = bool(profile.protected)
    if profile.created_at:
        p.account_created_at = profile.created_at
    if profile.raw:
        p.raw = profile.raw
    p.profile_synced_at = now
    return p, changes
