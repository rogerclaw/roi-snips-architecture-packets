from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..adapters.grok_web_search import GrokWebSearchAdapter


OFFICIAL_HINTS = ("investor", "ir.", "sec.gov", "businesswire", "globenewswire", "prnewswire")
STRUCTURED_HINTS = ("benzinga", "nasdaq.com", "marketwatch", "reuters", "bloomberg", "seekingalpha", "fda.gov", "sam.gov")
SOCIAL_HINTS = ("x.com", "twitter.com", "stocktwits", "reddit.com")


def classify_source_url(url: str) -> str:
    lower = url.lower()
    if any(hint in lower for hint in OFFICIAL_HINTS):
        return "official"
    if any(hint in lower for hint in SOCIAL_HINTS):
        return "social"
    if any(hint in lower for hint in STRUCTURED_HINTS):
        return "structured"
    return "structured"


def run_grok_web_verification(
    x_heat_radar: dict[str, Any],
    *,
    adapter: GrokWebSearchAdapter | None = None,
    required: bool = True,
) -> dict[str, Any]:
    adapter = adapter or GrokWebSearchAdapter()
    rows = []
    failures = []
    for candidate in x_heat_radar.get("candidates") or []:
        ticker = str(candidate.get("ticker") or "").upper()
        if not ticker:
            continue
        query = f"${ticker} stock catalyst official source SEC filing press release offering warrants why up today"
        result = adapter.search_web(query, limit=8)
        if not result.get("ok"):
            failures.append({"ticker": ticker, **{k: v for k, v in result.items() if k != "raw"}})
            continue
        buckets = {"official": [], "structured": [], "social": []}
        for url in [str(url) for url in result.get("citations") or [] if str(url).strip()]:
            buckets[classify_source_url(url)].append(url)
        content = str(result.get("content") or "")
        risk_text = content.lower()
        rows.append(
            {
                "ticker": ticker,
                "company": None,
                "verified_catalyst": bool(buckets["official"] or buckets["structured"]),
                "catalyst_type": "unknown_current_catalyst",
                "official_sources": buckets["official"],
                "structured_sources": buckets["structured"],
                "social_sources": sorted(set([*buckets["social"], *(candidate.get("key_threads") or [])])),
                "direct_beneficiary_score": 7 if buckets["official"] else (5 if buckets["structured"] else 0),
                "stale_news_risk": 7 if "2025" in content or "last year" in risk_text else 2,
                "dilution_or_offering_risk": 8 if "offering" in risk_text or "warrant" in risk_text or "dilution" in risk_text else 2,
                "already_priced_in_risk": 5 if "already" in risk_text and "priced" in risk_text else 3,
                "event_time_et": None,
                "verification_summary": content[:900],
            }
        )
    status = "completed" if rows else ("failed" if required else "partial")
    return {
        "stage": "grok_web_verification",
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verified_candidates": rows,
        "search_failures": failures,
    }
