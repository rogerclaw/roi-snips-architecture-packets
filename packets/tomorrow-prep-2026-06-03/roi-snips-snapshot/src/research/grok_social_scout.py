from __future__ import annotations

from typing import Any

from ..adapters.grok_search import GrokSearchAdapter


def scout_grok_x_social_candidates(tickers: list[str] | None = None, *, adapter: GrokSearchAdapter | None = None) -> dict[str, Any]:
    adapter = adapter or GrokSearchAdapter()
    result = adapter.fetch_x_candidates(tickers)
    result["role"] = "social_scout_research_only"
    result["can_authorize_live_trade"] = False
    return result
