from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from ..adapters.grok_x_search import GrokXSearchAdapter


TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")
DEFAULT_QUERY_FAMILIES = [
    "premarket gappers",
    "small cap runner",
    "FDA approval stock",
    "contract award stock",
    "merger stock",
    "short squeeze",
    "low float runner",
    "stock halt",
    "gap and go",
    "unusual volume",
    "watchlist premarket",
]


def _seed_symbols(seed_packet: dict[str, Any]) -> list[str]:
    symbols: set[str] = set()
    for value in seed_packet.values():
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                    if symbol:
                        symbols.add(symbol)
    return sorted(symbols)


def build_x_heat_queries(seed_packet: dict[str, Any], sources_config: dict[str, Any] | None = None) -> list[str]:
    symbols = _seed_symbols(seed_packet)
    query_families = list((sources_config or {}).get("query_families") or DEFAULT_QUERY_FAMILIES)
    queries = [f"${symbol} stock premarket why up catalyst" for symbol in symbols[:25]]
    queries.extend(query_families[:20])
    return queries


def run_grok_x_heat_radar(
    seed_packet: dict[str, Any],
    *,
    adapter: GrokXSearchAdapter | None = None,
    sources_config: dict[str, Any] | None = None,
    required: bool = True,
) -> dict[str, Any]:
    adapter = adapter or GrokXSearchAdapter()
    queries = build_x_heat_queries(seed_packet, sources_config)
    searches = adapter.run_queries(queries, limit=8) if queries else []
    counts: Counter[str] = Counter()
    citations: dict[str, set[str]] = defaultdict(set)
    snippets: dict[str, list[str]] = defaultdict(list)
    failures = []
    for result in searches:
        if not result.get("ok"):
            failures.append({k: v for k, v in result.items() if k != "raw"})
            continue
        content = str(result.get("content") or "")
        urls = [str(url) for url in result.get("citations") or [] if str(url).strip()]
        for symbol in TICKER_RE.findall(content):
            counts[symbol] += max(1, len(urls))
            snippets[symbol].append(content[:1200])
            for url in urls:
                if "x.com" in url or "twitter.com" in url:
                    citations[symbol].add(url)

    candidates = [
        {
            "ticker": ticker,
            "cashtag_count_estimate": int(count),
            "narrative": (snippets.get(ticker) or [""])[0][:500],
            "key_threads": sorted(citations.get(ticker) or []),
            "first_seen_x_time": None,
            "attention_velocity_score": min(10, round(count * 1.5, 2)),
            "influencer_concentration_score": min(10, len(citations.get(ticker) or [])),
            "pump_language_score": 0,
            "rumor_flag": "rumor" in " ".join(snippets.get(ticker) or []).lower(),
            "catalyst_claims": snippets.get(ticker, [])[:3],
            "needs_verification": True,
            "why_it_may_matter_at_open": "X/cashtag attention may accelerate opening liquidity if verified by hard sources.",
        }
        for ticker, count in counts.most_common()
    ]
    status = "completed" if candidates else ("failed" if required else "partial")
    return {
        "stage": "grok_x_heat_radar",
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "x_candidate_count": len(candidates),
        "queries": queries,
        "search_failures": failures,
        "candidates": candidates,
        "top_x_narratives": [row["narrative"] for row in candidates[:10] if row.get("narrative")],
        "rejected_noise": [],
    }
