"""Optional X recent-search adapter."""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_get_json


class XOptionalAdapter:
    def __init__(self) -> None:
        self.bearer = os.getenv("X_BEARER_TOKEN")
        self.base_url = os.getenv("X_API_BASE_URL", "https://api.x.com").rstrip("/")

    def fetch_recent(self, query: str, max_results: int = 10) -> dict[str, Any]:
        if not self.bearer:
            return {"ok": False, "reason": "missing_x_bearer_token", "optional": True}

        url = f"{self.base_url}/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.bearer}", "Accept": "application/json"}
        res = http_get_json(url, headers=headers, params={"query": query, "max_results": max_results})
        if not res.ok:
            return {"ok": False, "reason": "x_http_error", "status": res.status, "error": res.error, "optional": True}

        data = (res.data or {}).get("data") or []
        return {"ok": True, "count": len(data), "tweets": data}
