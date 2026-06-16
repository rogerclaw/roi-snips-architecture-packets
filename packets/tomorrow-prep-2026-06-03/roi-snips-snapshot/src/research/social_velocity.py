from __future__ import annotations

from typing import Any


PUMP_TERMS = {"guaranteed", "no risk", "moon", "100x", "easy money", "can't lose", "load the boat"}


def grok_x_narrative_from_events(ticker: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    symbol = str(ticker or "").upper().strip()
    related = [
        event
        for event in events
        if symbol in {str(item).upper().strip() for item in event.get("ticker_candidates") or []}
        and ("grok" in str(event.get("source_name") or "").lower() or "x" in str(event.get("source_name") or "").lower() or event.get("social_flag"))
    ]
    corroborating = [
        event
        for event in events
        if symbol in {str(item).upper().strip() for item in event.get("ticker_candidates") or []}
        and (event.get("official_flag") or event.get("structured_flag"))
    ]
    text = " ".join(f"{event.get('headline') or ''} {event.get('raw_text') or ''}" for event in related).lower()
    pump_hits = sorted(term for term in PUMP_TERMS if term in text)
    urls = [event.get("source_url") for event in related if event.get("source_url")]
    timestamps = [event.get("published_at") or event.get("discovered_at") for event in related if event.get("published_at") or event.get("discovered_at")]
    mentions = sum(max(1, len(event.get("ticker_candidates") or [])) for event in related)
    return {
        "ticker": symbol,
        "cashtag_mentions": mentions,
        "x_attention_velocity": min(10.0, mentions * 1.5),
        "narrative_summary": related[0].get("headline") if related else None,
        "key_threads": urls[:10],
        "influencer_concentration": None,
        "market_moving_hype_score": min(10.0, mentions * 1.2),
        "pump_language_score": min(10.0, len(pump_hits) * 2.5),
        "pump_language_terms": pump_hits,
        "rumor_vs_catalyst_flag": "social_only" if related and not corroborating else "corroborated_or_none",
        "source_urls": urls,
        "source_timestamps": timestamps,
    }
