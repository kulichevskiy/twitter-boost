import httpx
import pytest
import respx

from app.sources.twitterapi_io import TwitterApiIoSource
from app.sources.types import AccountRef, OutOfCredits

BASE = "https://api.twitterapi.io"


@pytest.fixture
def src():
    return TwitterApiIoSource("key", BASE)


@respx.mock
async def test_followers_ids_paginates_and_dedupes(src):
    route = respx.get(f"{BASE}/twitter/user/followers_ids")
    route.side_effect = [
        httpx.Response(200, json={"ids": ["1", "2", "3"], "has_next_page": True, "next_cursor": "c1", "status": "success"}),
        httpx.Response(200, json={"ids": ["3", "4"], "has_next_page": False, "next_cursor": "0", "status": "success"}),
    ]
    ids = [u.id async for u in src.iter_followers(AccountRef(id="42", handle="me"))]
    assert ids == ["1", "2", "3", "4"]
    assert route.calls[0].request.url.params["userId"] == "42"
    assert route.calls[1].request.url.params["cursor"] == "c1"
    assert src.counter.requests == 2


@respx.mock
async def test_followings_map_snake_profiles(src):
    respx.get(f"{BASE}/twitter/user/followings").mock(
        return_value=httpx.Response(
            200,
            json={
                "followings": [
                    {
                        "id": "77",
                        "screen_name": "jane",
                        "name": "Jane",
                        "description": "builds things",
                        "followers_count": 1200,
                        "friends_count": 300,
                        "statuses_count": 4000,
                        "profile_image_url_https": "https://pbs/x.jpg",
                        "created_at": "Wed Dec 19 20:20:32 +0000 2007",
                        "isBlueVerified": True,
                    }
                ],
                "has_next_page": False,
                "next_cursor": "",
                "status": "success",
            },
        )
    )
    users = [u async for u in src.iter_following(AccountRef(id="42", handle="me"))]
    assert len(users) == 1
    p = users[0].profile
    assert (p.id, p.handle, p.followers_count, p.following_count, p.tweets_count) == ("77", "jane", 1200, 300, 4000)
    assert p.verified is True and p.created_at.year == 2007


@respx.mock
async def test_batch_users_and_tweets(src):
    respx.get(f"{BASE}/twitter/user/batch_info_by_ids").mock(
        return_value=httpx.Response(
            200,
            json={"users": [{"id": "5", "userName": "bob", "name": "Bob", "followers": 10, "following": 5, "statusesCount": 1, "createdAt": "2020-01-02T03:04:05.000000Z"}], "status": "success"},
        )
    )
    users = await src.get_users(["5"])
    assert users[0].handle == "bob" and users[0].created_at.year == 2020
    respx.get(f"{BASE}/twitter/user/last_tweets").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"tweets": [{"id": "900", "text": "hi", "createdAt": "Tue Dec 10 07:00:30 +0000 2024", "likeCount": 3, "isReply": False, "url": "https://x.com/bob/status/900"}]},
                "has_next_page": False,
                "next_cursor": "",
            },
        )
    )
    tweets = await src.get_user_tweets("5", "bob", 50, False)
    assert tweets[0].metrics["likes"] == 3 and tweets[0].created_at.year == 2024


@respx.mock
async def test_out_of_credits_is_fatal(src):
    respx.get(f"{BASE}/twitter/user/info").mock(return_value=httpx.Response(402, json={"error": "Unauthorized"}))
    with pytest.raises(OutOfCredits):
        await src.me(AccountRef(id=None, handle="me"))


@respx.mock
async def test_status_error_body_raises(src):
    respx.get(f"{BASE}/twitter/user/info").mock(return_value=httpx.Response(200, json={"status": "error", "msg": "user not found"}))
    assert await src.get_user_by_handle("ghost") is None
