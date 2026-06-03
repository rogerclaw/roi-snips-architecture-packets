"""StockTwits symbol stream adapter."""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_get_json


class StockTwitsStreamAdapter:
    def __init__(self, base_url: str = "https://api.stocktwits.com/api/2", timeout_seconds: int | None = None) -> None:
        self.base_url = os.getenv("STOCKTWITS_BASE_URL", base_url).rstrip("/")
        self.timeout_seconds = int(timeout_seconds or os.getenv("STOCKTWITS_TIMEOUT_SECONDS", "5"))

    def fetch_symbol_stream(self, symbol: str, *, limit: int = 30) -> dict[str, Any]:
        cleaned = str(symbol or "").upper().strip()
        if not cleaned:
            return {"ok": False, "reason": "missing_stocktwits_symbol", "messages": []}
        res = http_get_json(f"{self.base_url}/streams/symbol/{cleaned}.json", params={"limit": limit}, timeout=self.timeout_seconds)
        if not res.ok:
            return {"ok": False, "reason": "stocktwits_http_error", "status": res.status, "error": res.error, "messages": []}
        messages = []
        for item in (res.data or {}).get("messages") or []:
            messages.append(
                {
                    "id": item.get("id"),
                    "created_at": item.get("created_at"),
                    "body": item.get("body"),
                    "sentiment": ((item.get("entities") or {}).get("sentiment") or {}).get("basic"),
                    "user_followers": ((item.get("user") or {}).get("followers")),
                }
            )
        return {"ok": True, "symbol": cleaned, "messages": messages, "count": len(messages)}
