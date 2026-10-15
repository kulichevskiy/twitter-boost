from app.db import session_scope
from app.schemas import PeopleFilter
from app.services import people
from app.services.settings import load_effective
from app.services.sync import run_sync


async def _seed():
    with session_scope() as s:
        eff = load_effective(s)
    await run_sync(eff)


async def test_relation_filters_add_up():
    await _seed()
    with session_scope() as s:
        total = people.search(s, PeopleFilter(page_size=1)).total
        mutual = people.search(s, PeopleFilter(relation="mutual", page_size=1)).total
        fo = people.search(s, PeopleFilter(relation="follower_only", page_size=1)).total
        go = people.search(s, PeopleFilter(relation="following_only", page_size=1)).total
    assert total == mutual + fo + go == 140
    assert (mutual, fo, go) == (70, 50, 20)


async def test_text_and_followers_filters():
    await _seed()
    with session_scope() as s:
        res = people.search(s, PeopleFilter(q="founder", followers_min=100, sort="-followers", page_size=10))
        assert res.total >= 1
        counts = [p.followers_count for p in res.items]
        assert counts == sorted(counts, reverse=True)
        assert all("founder" in ((p.handle or "") + (p.name or "") + (p.bio or "")).lower() for p in res.items)
        none = people.search(s, PeopleFilter(has_analysis=True, page_size=1))
        assert none.total == 0


async def test_stage_filter_with_deadline_sort_and_pipeline():
    from sqlalchemy import select

    from app.db import session_scope as scope
    from app.models import Person
    from app.services import pipeline

    await _seed()
    with scope() as s:
        eff = load_effective(s)
        ids = [r[0] for r in s.execute(select(Person.id).limit(3)).all()]
        for i, pid in enumerate(ids):
            pipeline.set_stage(s, s.get(Person, pid), "followed" if i < 2 else "ignored", eff)
    with scope() as s:
        res = people.search(s, PeopleFilter(stage=["followed"], sort="deadline"))
        assert res.total == 2 and all(p.stage == "followed" for p in res.items)
        res2 = people.search(s, PeopleFilter(stage=["followed", "ignored"], overdue=False, sort="-deadline"))
        assert res2.total == 3
        ids2 = people.ids_for_filter(s, PeopleFilter(stage=["ignored"]), 10)
        assert len(ids2) == 1
