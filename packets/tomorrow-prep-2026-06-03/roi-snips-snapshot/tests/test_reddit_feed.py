from src.adapters.reddit_feed import RedditFeedAdapter
from src.common.http_utils import HttpResponse


def test_reddit_feed_uses_public_json_without_credentials(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)

    seen = {}

    def fake_get(url, headers=None, params=None, timeout=20):
        seen["url"] = url
        seen["headers"] = headers or {}
        return HttpResponse(
            ok=True,
            status=200,
            data={
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "abc",
                                "title": "$MRAM unusual volume into open",
                                "selftext": "Watching $MRAM",
                                "created_utc": 1779300000,
                                "score": 12,
                                "num_comments": 4,
                                "permalink": "/r/stocks/comments/abc/test/",
                            }
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr("src.adapters.reddit_feed.http_get_json", fake_get)

    res = RedditFeedAdapter().fetch_themes(subreddits=["stocks"], limit_per_subreddit=1)

    assert res["ok"]
    assert res["auth_mode"] == "public_json"
    assert seen["url"] == "https://www.reddit.com/r/stocks/new.json"
    assert "Authorization" not in seen["headers"]
    assert res["trending"] == [{"ticker": "MRAM", "mentions": 2}]


def test_reddit_feed_prefers_oauth_when_credentials_exist(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "client")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")

    seen = {}

    def fake_post(*args, **kwargs):
        return HttpResponse(ok=True, status=200, data={"access_token": "token"})

    def fake_get(url, headers=None, params=None, timeout=20):
        seen["url"] = url
        seen["headers"] = headers or {}
        return HttpResponse(ok=True, status=200, data={"data": {"children": []}})

    monkeypatch.setattr("src.adapters.reddit_feed.http_post_form_json", fake_post)
    monkeypatch.setattr("src.adapters.reddit_feed.http_get_json", fake_get)

    res = RedditFeedAdapter().fetch_themes(subreddits=["stocks"], limit_per_subreddit=1)

    assert res["ok"]
    assert res["auth_mode"] == "oauth"
    assert seen["url"] == "https://oauth.reddit.com/r/stocks/new"
    assert seen["headers"]["Authorization"] == "bearer token"
