from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


RAW_DISCOVERY_BUCKETS = [
    "top_premarket_gainers",
    "highest_premarket_dollar_volume_gainers",
    "high_relative_volume_names",
    "fresh_official_catalyst_names",
    "structured_news_catalyst_names",
    "small_mid_micro_cap_gappers",
    "same_theme_laggards",
    "sector_sympathy_movers",
    "fda_biotech_names",
    "government_contract_policy_names",
    "mna_strategic_review_names",
    "retail_social_velocity_names",
    "prior_day_runners_with_new_catalyst_or_second_leg",
]


def _symbols(event: dict[str, Any]) -> list[str]:
    return [str(symbol).upper().strip() for symbol in event.get("ticker_candidates") or [] if str(symbol).strip()]


def _bucket_for_event(event: dict[str, Any]) -> str:
    source = str(event.get("source_name") or "").lower()
    catalyst = str(event.get("catalyst_type") or "").lower()
    notes = " ".join(str(note).lower() for note in event.get("notes") or [])
    text = f"{source} {catalyst} {notes} {event.get('headline') or ''} {event.get('raw_text') or ''}".lower()
    if "fda" in text or "clinical" in text or "biotech" in text:
        return "fda_biotech_names"
    if "government" in text or "sam.gov" in text or "chips" in text or "contract" in text or "award" in text:
        return "government_contract_policy_names"
    if "merger" in text or "acquisition" in text or "strategic" in text:
        return "mna_strategic_review_names"
    if event.get("social_flag") or "stocktwits" in source or "reddit" in source or "grok" in source or "x" == source:
        return "retail_social_velocity_names"
    if event.get("official_flag"):
        return "fresh_official_catalyst_names"
    if event.get("structured_flag"):
        return "structured_news_catalyst_names"
    if "mover" in source or "gapper" in text:
        return "top_premarket_gainers"
    return "sector_sympathy_movers"


def build_raw_runner_candidates(events: list[dict[str, Any]], *, preserve_top_n: int = 25) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    touches: dict[str, int] = defaultdict(int)
    for event in events:
        bucket = _bucket_for_event(event)
        for ticker in _symbols(event):
            touches[ticker] += 1
            row = by_symbol.get(ticker)
            if row is None:
                row = {
                    "ticker": ticker,
                    "company": event.get("company_name"),
                    "source_lane": event.get("source_name") or bucket,
                    "first_seen_at_utc": event.get("discovered_at") or event.get("published_at") or datetime.now(timezone.utc).isoformat(),
                    "raw_reason": bucket,
                    "raw_catalyst": event.get("headline") or event.get("raw_text") or event.get("catalyst_type"),
                    "raw_source_url": event.get("source_url"),
                    "price": event.get("price") or event.get("last_price") or event.get("current_price") or 0,
                    "gap_pct": event.get("gap_pct") or 0,
                    "premarket_volume": event.get("premarket_volume") or 0,
                    "premarket_dollar_volume": event.get("premarket_dollar_volume") or 0,
                    "pre_filter_flags": [],
                    "raw_buckets": [],
                    "source_urls": [],
                    "source_lanes": [],
                }
                by_symbol[ticker] = row
            if bucket not in row["raw_buckets"]:
                row["raw_buckets"].append(bucket)
            source_url = event.get("source_url")
            if source_url and source_url not in row["source_urls"]:
                row["source_urls"].append(source_url)
            source_lane = event.get("source_name") or bucket
            if source_lane and source_lane not in row["source_lanes"]:
                row["source_lanes"].append(source_lane)
            if event.get("official_flag"):
                row["pre_filter_flags"].append("official_catalyst")
            if event.get("structured_flag"):
                row["pre_filter_flags"].append("structured_catalyst")
            if event.get("social_flag"):
                row["pre_filter_flags"].append("social_velocity")
    rows = list(by_symbol.values())
    for row in rows:
        row["raw_touch_count"] = touches[row["ticker"]]
        row["pre_filter_flags"] = sorted(set(row["pre_filter_flags"]))
    rows.sort(
        key=lambda row: (
            int(row.get("raw_touch_count") or 0),
            float(row.get("premarket_dollar_volume") or 0.0),
            abs(float(row.get("gap_pct") or 0.0)),
            row.get("ticker") or "",
        ),
        reverse=True,
    )
    return rows[: max(1, preserve_top_n)]


def summarize_raw_discovery(raw_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    sources: set[str] = set()
    buckets: set[str] = set()
    for row in raw_candidates:
        sources.update(str(item) for item in row.get("source_lanes") or [] if item)
        buckets.update(str(item) for item in row.get("raw_buckets") or [] if item)
    return {
        "raw_candidate_count": len(raw_candidates),
        "raw_candidate_sources": sorted(sources),
        "raw_candidate_buckets": sorted(buckets),
        "target_raw_candidates_min": 100,
        "target_raw_candidates_max": 250,
        "acceptable_raw_candidates_min": 50,
        "degraded_raw_candidates_min": 25,
        "severely_degraded_raw_candidates_min": 10,
        "preserved_top_raw_candidates": min(len(raw_candidates), 250),
    }
