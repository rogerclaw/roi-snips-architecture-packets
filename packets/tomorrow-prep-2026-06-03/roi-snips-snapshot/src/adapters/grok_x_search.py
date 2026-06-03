from __future__ import annotations

from typing import Any

from .xai_responses import XAIResponsesAdapter


class GrokXSearchAdapter:
    """Research-only X Search wrapper for Grok-first discovery."""

    def __init__(self, client: XAIResponsesAdapter | None = None) -> None:
        self.client = client or XAIResponsesAdapter()

    def search_x(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        return self.client.search(query, tool="x_search", limit=limit)

    def run_queries(self, queries: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
        return [self.search_x(query, limit=limit) for query in queries]

    def readiness_probe(self) -> dict[str, Any]:
        result = self.search_x("$SPY stock market open", limit=1)
        return {"ok": bool(result.get("ok")), "tool": "x_search", "model": result.get("model"), "reason": result.get("reason")}
