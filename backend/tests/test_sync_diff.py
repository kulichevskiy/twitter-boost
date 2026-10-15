from sqlalchemy import func, select

from app.db import session_scope
from app.models import Contact, Event, Person, Relation, Sync
from app.services.settings import load_effective
from app.services.sync import run_sync
from app.sources import fake


async def _sync():
    with session_scope() as s:
        eff = load_effective(s)
    sid = await run_sync(eff, trigger="test")
    with session_scope() as s:
        sync = s.get(Sync, sid)
        s.expunge(sync)
        return sync


def _count(model, *where):
    with session_scope() as s:
        return s.execute(select(func.count()).select_from(model).where(*where)).scalar_one()


async def test_baseline_then_no_change():
    first = await _sync()
    assert first.status == "ok"
    assert first.kind == "baseline"
    assert first.followers_total == 120
    assert first.following_total == 90
    # baseline writes relations but no per-person events
    assert _count(Relation) == 120 + 90
    assert _count(Event) == 0
    with session_scope() as s:
        mutual = s.execute(select(func.count()).where(Person.is_follower.is_(True), Person.is_following.is_(True))).scalar_one()
    assert mutual == 70  # ids 50..119 overlap

    second = await _sync()
    assert second.kind == "full"
    assert second.status == "ok"
    assert (second.added_followers, second.removed_followers, second.added_following, second.removed_following) == (0, 0, 0, 0)
    assert _count(Event) == 0


async def test_unfollow_needs_two_confirmations():
    await _sync()
    fake.FakeSource().bump()  # epoch 1: -2 followers, +3 followers, +2 following
    s2 = await _sync()
    assert s2.added_followers == 3
    assert s2.added_following == 2
    assert s2.removed_followers == 0  # first miss only bumps the streak
    assert _count(Event, Event.type == "followed_me") == 3
    assert _count(Event, Event.type == "i_followed") == 2
    assert _count(Event, Event.type == "unfollowed_me") == 0

    s3 = await _sync()  # same epoch: second consecutive miss confirms
    assert s3.removed_followers == 2
    assert _count(Event, Event.type == "unfollowed_me") == 2
    with session_scope() as s:
        gone = s.execute(select(Relation).where(Relation.direction == "follower", Relation.active.is_(False))).scalars().all()
        assert len(gone) == 2
        assert all(r.ended_at is not None for r in gone)
        for r in gone:
            assert s.get(Person, r.person_id).is_follower is False


async def test_i_followed_creates_pipeline_contact():
    await _sync()
    fake.FakeSource().bump()
    await _sync()
    with session_scope() as s:
        contacts = s.execute(select(Contact)).scalars().all()
        assert len(contacts) == 2
        assert {c.stage for c in contacts} == {"followed"}
        assert all(c.deadline_at is not None and c.followed_at is not None for c in contacts)
