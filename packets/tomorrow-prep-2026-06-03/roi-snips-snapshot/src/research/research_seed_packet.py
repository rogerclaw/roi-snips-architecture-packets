from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .trade_authorization_ticket import BLOCKED_DEFAULT_MEGACAPS


def build_research_seed_packet(
    *,
    trading_date: str,
    source_lane_status: list[dict[str, Any]] | None = None,
    top_premarket_gainers: list[dict[str, Any]] | None = None,
    top_premarket_dollar_volume: list[dict[str, Any]] | None = None,
    high_rvol: list[dict[str, Any]] | None = None,
    fresh_news: list[dict[str, Any]] | None = None,
    sec_filings: list[dict[str, Any]] | None = None,
    company_ir: list[dict[str, Any]] | None = None,
    benzinga_alpaca_news: list[dict[str, Any]] | None = None,
    stocktwits_retail_heat: list[dict[str, Any]] | None = None,
    grok_x_social_candidates: list[dict[str, Any]] | None = None,
    reddit_candidates: list[dict[str, Any]] | None = None,
    government_policy_candidates: list[dict[str, Any]] | None = None,
    fda_biotech_candidates: list[dict[str, Any]] | None = None,
    scheduled_event_candidates: list[dict[str, Any]] | None = None,
    prior_winners: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lanes = {
        "top_premarket_gainers": top_premarket_gainers or [],
        "top_premarket_dollar_volume": top_premarket_dollar_volume or [],
        "high_rvol": high_rvol or [],
        "fresh_news": fresh_news or [],
        "sec_filings": sec_filings or [],
        "company_ir": company_ir or [],
        "benzinga_alpaca_news": benzinga_alpaca_news or [],
        "stocktwits_retail_heat": stocktwits_retail_heat or [],
        "grok_x_social_candidates": grok_x_social_candidates or [],
        "reddit_candidates": reddit_candidates or [],
        "government_policy_candidates": government_policy_candidates or [],
        "fda_biotech_candidates": fda_biotech_candidates or [],
        "scheduled_event_candidates": scheduled_event_candidates or [],
    }
    seen: set[str] = set()
    for rows in lanes.values():
        for row in rows:
            symbol = str((row or {}).get("ticker") or (row or {}).get("symbol") or "").upper()
            if symbol:
                seen.add(symbol)
    missing_lanes = [name for name, rows in lanes.items() if not rows]
    has_mover = bool(lanes["top_premarket_gainers"] or lanes["top_premarket_dollar_volume"] or lanes["high_rvol"])
    has_web = bool(lanes["fresh_news"] or lanes["sec_filings"] or lanes["company_ir"] or lanes["benzinga_alpaca_news"])
    has_social = bool(lanes["stocktwits_retail_heat"] or lanes["grok_x_social_candidates"] or lanes["reddit_candidates"])
    quality = "OK" if len(seen) >= 25 and has_mover and has_web and has_social else "DEGRADED"
    return {
        "trading_date": trading_date,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "market_session": "PREMARKET_OR_EARLY_SESSION",
        **lanes,
        "source_lane_status": source_lane_status or [],
        "missing_lanes": missing_lanes,
        "prior_winners": prior_winners or [],
        "blocked_default_megacaps": sorted(BLOCKED_DEFAULT_MEGACAPS),
        "account_constraints": {"max_notional_usd": 900, "long_only": True, "one_position_max": True},
        "candidate_count": len(seen),
        "seed_packet_quality": quality,
    }
