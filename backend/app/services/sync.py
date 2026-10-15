"""Snapshot sync: pull both lists, hydrate new profiles, diff against the
stored relations and write events. See README for the algorithm."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import zstandard
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Account, Event, Person, Relation, Snapshot, Sync, XToken, utcnow
from ..sources.registry import open_sources, source_name_for
from ..sources.types import AccountRef, UserProfile
from . import pipeline
from .people import upsert_profile
from .settings import Effective

log = logging.getLogger(__name__)


class SyncError(Exception):
    pass


@dataclass
class ListResult:
    ids: list[str] = field(default_factory=list)
    profiles: dict[str, UserProfile] = field(default_factory=dict)


def compress_ids(ids: list[str]) -> bytes:
    return zstandard.ZstdCompressor(level=6).compress(",".join(sorted(ids)).encode())


def decompress_ids(blob: bytes) -> list[str]:
    raw = zstandard.ZstdDecompressor().decompress(blob).decode()
    return raw.split(",") if raw else []


def resolve_account(session: Session, eff: Effective) -> AccountRef:
    acc = session.get(Account, 1)
    tok = session.get(XToken, 1)
    user_id = (acc.user_id if acc else None) or (tok.user_id if tok else None)
    handle = (acc.handle if acc else None) or (tok.handle if tok else None) or (eff.my_handle or None)
    return AccountRef(id=user_id, handle=handle)


def next_sync_at(session: Session, eff: Effective, now: datetime | None = None) -> datetime | None:
    """When the scheduler should run the next sync (UTC naive). A value in the
    past means "due now". Failed syncs count as attempts so a broken config
    does not retry every minute."""
    now = now or utcnow()
    if eff.sync_schedule_mode == "off":
        return None
    last = session.execute(select(Sync.started_at).order_by(Sync.started_at.desc()).limit(1)).scalar_one_or_none()
    if eff.sync_schedule_mode == "interval":
        if last is None:
            return now
        return last + timedelta(hours=max(1, eff.sync_interval_hours))
    # daily at HH:MM local time; everything else in the app is UTC naive
    try:
        hh, mm = (int(x) for x in eff.sync_daily_time.split(":"))
    except ValueError:
        hh, mm = 6, 0
    local_now = datetime.now()
    offset = local_now - now
    candidate = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0) - offset
    if last is not None and last >= candidate:
        return candidate + timedelta(days=1)
    if last is None and candidate <= now:
        # Never synced and today's slot has passed: run on first start.
        return now
    return candidate


async def _collect(it, result: ListResult) -> None:
    async for su in it:  # type: SourceUser
        result.ids.append(su.id)
        if su.profile is not None:
            result.profiles[su.id] = su.profile


def _tolerance(expected: int | None, eff: Effective) -> int:
    if expected is None:
        return 10**9
    return max(eff.count_tolerance_abs, int(expected * eff.count_tolerance_pct / 100))


async def run_sync(eff: Effective, trigger: str = "manual") -> int:
    """Run one full sync. Returns the sync id. Never raises for source errors:
    the sync row records status=failed with the message."""
    with session_scope() as session:
        ref = resolve_account(session, eff)
        is_baseline = (
            session.execute(select(Sync.id).where(Sync.status.in_(("ok", "suspicious"))).limit(1)).scalar_one_or_none()
            is None
        )
        sync = Sync(source=source_name_for(eff, "lists"), kind="baseline" if is_baseline else "full", notes={"trigger": trigger})
        session.add(sync)
        session.flush()
        sync_id = sync.id

    followers, following = ListResult(), ListResult()
    me: UserProfile | None = None
    try:
        async with open_sources(eff, ["lists", "profiles"]) as (src, counter):
            lists = src["lists"]
            me = await lists.me(ref)
            if ref.id is None:
                ref = AccountRef(id=me.id, handle=me.handle or ref.handle)
            await _collect(lists.iter_followers(ref), followers)
            await _collect(lists.iter_following(ref), following)
            requests_after_lists = counter.requests
            refreshed = await _hydrate(src["profiles"], eff, followers, following)
            total_requests = counter.requests
    except Exception as exc:
        log.exception("sync %s failed", sync_id)
        with session_scope() as session:
            sync = session.get(Sync, sync_id)
            sync.status = "failed"
            sync.error = f"{type(exc).__name__}: {exc}"[:2000]
            sync.finished_at = utcnow()
        return sync_id

    with session_scope() as session:
        sync = session.get(Sync, sync_id)
        now = utcnow()
        _update_account(session, me, ref, now)
        sync.followers_total = len(set(followers.ids))
        sync.following_total = len(set(following.ids))
        sync.followers_expected = me.followers_count
        sync.following_expected = me.following_count
        sync.requests = total_requests
        sync.notes = {**(sync.notes or {}), "requests_lists": requests_after_lists}
        session.add(Snapshot(sync_id=sync_id, direction="follower", count=sync.followers_total, ids_blob=compress_ids(followers.ids)))
        session.add(Snapshot(sync_id=sync_id, direction="following", count=sync.following_total, ids_blob=compress_ids(following.ids)))

        bad: list[str] = []
        if abs(sync.followers_total - (me.followers_count or sync.followers_total)) > _tolerance(me.followers_count, eff):
            bad.append(f"followers: got {sync.followers_total}, profile says {me.followers_count}")
        if abs(sync.following_total - (me.following_count or sync.following_total)) > _tolerance(me.following_count, eff):
            bad.append(f"following: got {sync.following_total}, profile says {me.following_count}")
        if bad:
            sync.status = "suspicious"
            sync.error = "; ".join(bad)
            sync.finished_at = now
            # Still store fresh profile data: it's harmless and already paid for.
            for prof in list(followers.profiles.values()) + list(following.profiles.values()):
                upsert_profile(session, prof, now)
            sync.profiles_refreshed = refreshed
            return sync_id

        baseline = sync.kind == "baseline"
        events: list[Event] = []
        a_f, r_f = _apply_direction(session, "follower", followers, sync_id, now, eff, baseline, events)
        a_g, r_g = _apply_direction(session, "following", following, sync_id, now, eff, baseline, events)
        sync.added_followers, sync.removed_followers = a_f, r_f
        sync.added_following, sync.removed_following = a_g, r_g
        sync.profiles_refreshed = refreshed
        _refresh_flags(session, now)
        for ev in events:
            person = session.get(Person, ev.person_id)
            if person is not None:
                pipeline.apply_event(session, person, ev.type, eff, ev.at)
        overdue = pipeline.mark_overdue(session, eff, now)
        sync.notes = {**(sync.notes or {}), "events": len(events), "overdue_marked": overdue}
        sync.status = "ok"
        sync.finished_at = utcnow()
    return sync_id


async def _hydrate(profiles_src, eff: Effective, followers: ListResult, following: ListResult) -> int:
    """Fetch profiles for ids we have never seen, plus a batch of stale ones."""
    have = {**followers.profiles, **following.profiles}
    all_ids = set(followers.ids) | set(following.ids)
    with session_scope() as session:
        known = {
            pid: synced
            for pid, synced in session.execute(select(Person.id, Person.profile_synced_at)).all()
        }
    missing = [pid for pid in all_ids if pid not in have and pid not in known]
    stale_cutoff = utcnow() - timedelta(days=eff.profile_refresh_days)
    stale = sorted(
        (pid for pid in all_ids if pid not in have and pid in known and (known[pid] is None or known[pid] < stale_cutoff)),
        key=lambda pid: known[pid] or datetime.min,
    )[: eff.profile_refresh_batch]
    todo = missing + stale
    if not todo:
        return 0
    fetched = await profiles_src.get_users(todo)
    for prof in fetched:
        have[prof.id] = prof
        if prof.id in set(followers.ids):
            followers.profiles[prof.id] = prof
        if prof.id in set(following.ids):
            following.profiles[prof.id] = prof
    return len(fetched)


def _update_account(session: Session, me: UserProfile, ref: AccountRef, now: datetime) -> None:
    acc = session.get(Account, 1) or Account(id=1)
    acc.user_id = me.id or ref.id
    acc.handle = me.handle or ref.handle
    acc.name = me.name
    acc.avatar_url = me.avatar_url
    acc.followers_count = me.followers_count
    acc.following_count = me.following_count
    acc.synced_at = now
    acc.raw = me.raw
    hist = list(acc.history or [])
    hist.append({"at": now.isoformat(), "followers": me.followers_count, "following": me.following_count})
    acc.history = hist[-400:]
    session.add(acc)


def _apply_direction(
    session: Session,
    direction: str,
    data: ListResult,
    sync_id: int,
    now: datetime,
    eff: Effective,
    baseline: bool,
    events: list[Event],
) -> tuple[int, int]:
    gained = "followed_me" if direction == "follower" else "i_followed"
    lost = "unfollowed_me" if direction == "follower" else "i_unfollowed"
    current = set(data.ids)
    existing: dict[str, Relation] = {
        r.person_id: r for r in session.execute(select(Relation).where(Relation.direction == direction)).scalars()
    }
    added = removed = 0

    for pid in current:
        prof = data.profiles.get(pid)
        changes: dict[str, Any] = {}
        if prof is not None:
            person, changes = upsert_profile(session, prof, now)
        else:
            person = session.get(Person, pid)
            if person is None:
                person = Person(id=pid, first_seen_at=now)
                session.add(person)
        if changes and not baseline:
            ev = Event(person_id=pid, type="profile_changed", at=now, sync_id=sync_id, payload=changes)
            session.add(ev)
            person.last_event_at = now
        rel = existing.get(pid)
        if rel is None:
            session.add(Relation(person_id=pid, direction=direction, active=True, first_seen_at=now, last_seen_at=now))
            added += 1
            if not baseline:
                ev = Event(person_id=pid, type=gained, at=now, sync_id=sync_id)
                session.add(ev)
                events.append(ev)
                person.last_event_at = now
        else:
            rel.last_seen_at = now
            rel.missing_streak = 0
            if not rel.active:
                rel.active = True
                rel.ended_at = None
                added += 1
                ev = Event(person_id=pid, type=gained, at=now, sync_id=sync_id, payload={"again": True})
                session.add(ev)
                events.append(ev)
                person.last_event_at = now

    for pid, rel in existing.items():
        if pid in current or not rel.active:
            continue
        rel.missing_streak += 1
        if rel.missing_streak >= max(1, eff.unfollow_confirmations):
            rel.active = False
            rel.ended_at = now
            removed += 1
            ev = Event(person_id=pid, type=lost, at=now, sync_id=sync_id, payload={"missed_syncs": rel.missing_streak})
            session.add(ev)
            events.append(ev)
            person = session.get(Person, pid)
            if person is not None:
                person.last_event_at = now
    session.flush()
    return added, removed


def _refresh_flags(session: Session, now: datetime) -> None:
    """Recompute Person.is_follower / is_following from active relations."""
    active = session.execute(select(Relation.person_id, Relation.direction).where(Relation.active.is_(True))).all()
    followers = {pid for pid, d in active if d == "follower"}
    following = {pid for pid, d in active if d == "following"}
    for person in session.execute(select(Person)).scalars():
        f, g = person.id in followers, person.id in following
        if person.is_follower != f:
            person.is_follower = f
        if person.is_following != g:
            person.is_following = g
    session.flush()
