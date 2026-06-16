"""Reddit ingestion adapter.

OAuth client-credentials are preferred when configured, but the scout can also
use Reddit's public JSON listing endpoints. The public path keeps social
discovery useful without requiring a personal Reddit account.
"""

from __future__ import annotations

import os
import re
from typing import Any

from ..common.http_utils import http_get_json, http_post_form_json


TICKER_DOLLAR_RE = re.compile(r"\$([A-Z]{1,5})\b")


class RedditFeedAdapter:
    def __init__(self) -> None:
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "roi-snips/1.0")

    def _token(self) -> dict[str, Any]:
        if not self.client_id or not self.client_secret:
            return {"ok": False, "reason": "missing_reddit_credentials"}
        res = http_post_form_json(
            "https://www.reddit.com/api/v1/access_token",
            form={"grant_type": "client_credentials"},
            headers={"User-Agent": self.user_agent},
            basic_auth=(self.client_id, self.client_secret),
        )
        if not res.ok:
            return {"ok": False, "reason": "reddit_token_error", "status": res.status, "error": res.error}
        token = (res.data or {}).get("access_token")
        if not token:
            return {"ok": False, "reason": "reddit_token_missing"}
        return {"ok": True, "token": token}

    def fetch_themes(self, subreddits: list[str] | None = None, limit_per_subreddit: int = 25) -> dict[str, Any]:
        token_res = self._token()
        subreddits = subreddits or ["stocks", "wallstreetbets", "investing", "StockMarket"]
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        oauth_available = bool(token_res.get("ok"))
        if oauth_available:
            headers["Authorization"] = f"bearer {token_res['token']}"

        posts: list[dict[str, Any]] = []
        ticker_counts: dict[str, int] = {}
        for sub in subreddits:
            url = f"https://oauth.reddit.com/r/{sub}/new" if oauth_available else f"https://www.reddit.com/r/{sub}/new.json"
            res = http_get_json(url, headers=headers, params={"limit": limit_per_subreddit})
            if not res.ok:
                posts.append({"subreddit": sub, "error": res.error, "status": res.status})
                continue

            children = (((res.data or {}).get("data") or {}).get("children") or [])
            for child in children:
                d = child.get("data") or {}
                title = d.get("title") or ""
                body = d.get("selftext") or ""
                content = f"{title}\n{body}"
                symbols = TICKER_DOLLAR_RE.findall(content)
                for s in symbols:
                    ticker_counts[s] = ticker_counts.get(s, 0) + 1
                posts.append(
                    {
                        "subreddit": sub,
                        "id": d.get("id"),
                        "title": title,
                        "created_utc": d.get("created_utc"),
                        "score": d.get("score"),
                        "num_comments": d.get("num_comments"),
                        "tickers": sorted(set(symbols)),
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                    }
                )

        trending = sorted(
            [{"ticker": t, "mentions": c} for t, c in ticker_counts.items()],
            key=lambda x: x["mentions"],
            reverse=True,
        )

        if not posts and not oauth_available:
            return {
                "ok": False,
                "reason": token_res.get("reason") or "reddit_public_json_unavailable",
                "auth_mode": "public_json",
                "post_count": 0,
                "posts": [],
                "trending": [],
            }

        return {
            "ok": True,
            "auth_mode": "oauth" if oauth_available else "public_json",
            "credential_reason": None if oauth_available else token_res.get("reason"),
            "post_count": len(posts),
            "posts": posts,
            "trending": trending,
        }
