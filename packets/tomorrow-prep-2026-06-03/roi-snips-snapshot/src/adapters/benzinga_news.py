"""Benzinga news ingestion adapter (real HTTP path)."""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_get_json


class BenzingaNewsAdapter:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.benzinga.com") -> None:
        self.api_key = api_key or os.getenv("BENZINGA_API_KEY")
        self.base_url = os.getenv("BENZINGA_BASE_URL", base_url).rstrip("/")

    def fetch_events(self, page_size: int = 50, updated_since: str | None = None, tickers: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            return {"ok": False, "reason": "missing_benzinga_api_key"}

        url = f"{self.base_url}/api/v2/news"
        headers = {"Authorization": f"token {self.api_key}", "Accept": "application/json"}
        params = {"pageSize": page_size, "updatedSince": updated_since, "tickers": tickers}
        res = http_get_json(url, headers=headers, params=params)
        if not res.ok:
            return {"ok": False, "reason": "benzinga_http_error", "status": res.status, "error": res.error}

        payload = res.data if isinstance(res.data, list) else (res.data or [])
        events: list[dict[str, Any]] = []
        for item in payload:
            symbols = item.get("stocks") or item.get("symbols") or []
            tickers_out = []
            for s in symbols:
                if isinstance(s, dict):
                    ticker = s.get("name") or s.get("symbol")
                else:
                    ticker = str(s)
                if ticker:
                    tickers_out.append(ticker.upper())
            events.append(
                {
                    "id": item.get("id"),
                    "updated": item.get("updated") or item.get("updatedAt"),
                    "created": item.get("created") or item.get("createdAt"),
                    "title": item.get("title"),
                    "channels": item.get("channels") or [],
                    "tickers": sorted(set(tickers_out)),
                    "url": item.get("url"),
                }
            )

        return {"ok": True, "count": len(events), "events": events}
