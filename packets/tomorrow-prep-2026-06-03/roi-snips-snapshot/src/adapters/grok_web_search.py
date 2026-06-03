from __future__ import annotations

from typing import Any

from .xai_responses import XAIResponsesAdapter


class GrokWebSearchAdapter:
    """Research-only web search wrapper for Grok verification."""

    def __init__(self, client: XAIResponsesAdapter | None = None) -> None:
        self.client = client or XAIResponsesAdapter()

    def search_web(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        return self.client.search(query, tool="web_search", limit=limit)

    def run_queries(self, queries: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
        return [self.search_web(query, limit=limit) for query in queries]

    def readiness_probe(self) -> dict[str, Any]:
        result = self.search_web("current premarket stock catalyst official source", limit=1)
        return {"ok": bool(result.get("ok")), "tool": "web_search", "model": result.get("model"), "reason": result.get("reason")}
