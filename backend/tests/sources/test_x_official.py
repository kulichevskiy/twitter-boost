import httpx
import respx

from app.sources.types import AccountRef
from app.sources.x_official import XOfficialSource

BASE = "https://api.x.com"


async def _token():
    return "tok"


@respx.mock
async def test_followers_pagination_and_mapping():
    src = XOfficialSource(_token, BASE)
    route = respx.get(f"{BASE}/2/users/1/followers")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "data": [
                    {"id": "10", "username": "a", "name": "A", "public_metrics": {"followers_count": 5, "following_count": 2, "post_count": 9, "listed_count": 0}, "profile_image_url": "https://p/a_normal.jpg", "created_at": "2019-05-01T00:00:00.000Z"}
                ],
                "meta": {"next_token": "n1", "result_count": 1},
            },
        ),
        httpx.Response(200, json={"data": [{"id": "11", "username": "b", "name": "B"}], "meta": {"result_count": 1}}),
    ]
    users = [u async for u in src.iter_followers(AccountRef(id="1", handle="me"))]
    assert [u.id for u in users] == ["10", "11"]
    assert users[0].profile.avatar_url.endswith("_400x400.jpg")
    assert users[0].profile.tweets_count == 9
    assert route.calls[1].request.url.params["pagination_token"] == "n1"
    assert route.calls[0].request.headers["authorization"] == "Bearer tok"


@respx.mock
async def test_rate_limit_waits_then_succeeds(monkeypatch):
    import app.sources.x_official as mod

    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    src = XOfficialSource(_token, BASE)
    route = respx.get(f"{BASE}/2/users/me")
    route.side_effect = [
        httpx.Response(429, headers={"x-rate-limit-reset": str(int(__import__("time").time()) + 10)}),
        httpx.Response(200, json={"data": {"id": "1", "username": "me", "name": "Me", "public_metrics": {"followers_count": 3, "following_count": 4, "post_count": 1, "listed_count": 0}}}),
    ]
    me = await src.me(AccountRef(id="1", handle="me"))
    assert me.followers_count == 3
    assert len(sleeps) == 1 and 5 <= sleeps[0] <= 12


@respx.mock
async def test_user_tweets_exclude_param():
    src = XOfficialSource(_token, BASE)
    route = respx.get(f"{BASE}/2/users/7/tweets").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "1", "text": "x", "created_at": "2024-01-01T00:00:00.000Z", "public_metrics": {"like_count": 1, "repost_count": 0, "reply_count": 0, "quote_count": 0, "bookmark_count": 0, "impression_count": 50}, "referenced_tweets": [{"type": "replied_to", "id": "0"}]}], "meta": {"result_count": 1}},
        )
    )
    tweets = await src.get_user_tweets("7", "u", 20, include_replies=False)
    assert route.calls[0].request.url.params["exclude"] == "retweets,replies"
    assert tweets[0].is_reply is True and tweets[0].metrics["views"] == 50
