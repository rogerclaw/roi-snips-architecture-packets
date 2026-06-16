from __future__ import annotations

import os
from typing import Any


REQUIRED_SOURCE_LANES = [
    "Alpaca SIP",
    "Alpaca News",
    "Benzinga",
    "SEC EDGAR",
    "Company IR",
    "FMP movers",
    "StockTwits",
    "TradingView-style screener",
    "Grok/X",
    "Reddit",
    "Tavily/Brave/Exa",
    "Firecrawl/Crawl4AI",
    "openFDA",
    "ClinicalTrials.gov",
    "SAM.gov/USAspending",
    "Nasdaq halt feed",
]


SOURCE_TO_LANE = {
    "exchange_scout": "Alpaca News",
    "alpaca_news": "Alpaca News",
    "benzinga": "Benzinga",
    "sec_edgar": "SEC EDGAR",
    "sec_scout": "SEC EDGAR",
    "ir_scout": "Company IR",
    "external_movers_scout": "FMP movers",
    "top_gainers_scout": "FMP movers",
    "premarket_dollar_volume_scout": "FMP movers",
    "high_rvol_scout": "TradingView-style screener",
    "smallcap_catalyst_scout": "Benzinga",
    "stocktwits": "StockTwits",
    "stocktwits_stream": "StockTwits",
    "tradingview_screener": "TradingView-style screener",
    "grok_x": "Grok/X",
    "grok": "Grok/X",
    "reddit": "Reddit",
    "social_velocity_scout": "Grok/X",
    "tavily": "Tavily/Brave/Exa",
    "brave": "Tavily/Brave/Exa",
    "exa": "Tavily/Brave/Exa",
    "firecrawl": "Firecrawl/Crawl4AI",
    "crawl4ai": "Firecrawl/Crawl4AI",
    "fda_scout": "openFDA",
    "openfda": "openFDA",
    "clinicaltrials": "ClinicalTrials.gov",
    "government_scout": "SAM.gov/USAspending",
    "federal_catalyst_scout": "SAM.gov/USAspending",
    "sam_gov": "SAM.gov/USAspending",
    "usaspending": "SAM.gov/USAspending",
    "nasdaq_halt": "Nasdaq halt feed",
}


LANE_CREDENTIAL_HINTS = {
    "FMP movers": ["FMP_API_KEY"],
    "StockTwits": ["STOCKTWITS_ACCESS_TOKEN", "STOCKTWITS_BEARER_TOKEN"],
    "TradingView-style screener": ["ROI_SNIPS_ENABLE_TRADINGVIEW_SCREENER"],
    "Grok/X": ["XAI_API_KEY", "GROK_API_KEY"],
    "Tavily/Brave/Exa": ["TAVILY_API_KEY", "BRAVE_API_KEY", "EXA_API_KEY"],
    "Firecrawl/Crawl4AI": ["FIRECRAWL_API_KEY"],
    "openFDA": ["OPENFDA_API_KEY"],
    "SAM.gov/USAspending": ["SAM_GOV_API_KEY", "USASPENDING_API_KEY"],
}


def _lane_for_event(event: dict[str, Any]) -> str | None:
    source = str(event.get("source_name") or "").strip().lower()
    if source in SOURCE_TO_LANE:
        return SOURCE_TO_LANE[source]
    url = str(event.get("source_url") or "").lower()
    if "benzinga.com" in url:
        return "Benzinga"
    if "sec.gov" in url:
        return "SEC EDGAR"
    if "stocktwits" in url:
        return "StockTwits"
    if "x.com" in url or "twitter.com" in url:
        return "Grok/X"
    return None


def build_source_lane_status(events: list[dict[str, Any]], primary_ticker: str | None = None, errors: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    primary = str(primary_ticker or "").upper()
    rows: dict[str, dict[str, Any]] = {
        lane: {
            "lane_name": lane,
            "configured": True,
            "ran": False,
            "produced_candidates_count": 0,
            "produced_candidates": 0,
            "candidate_count": 0,
            "produced_useful_evidence_count": 0,
            "useful_for_primary": False,
            "affected_primary_selection": False,
            "affected_backup_list": False,
            "errors": [],
            "missing_credentials": [],
            "fallback_used": False,
        }
        for lane in REQUIRED_SOURCE_LANES
    }
    for lane, env_names in LANE_CREDENTIAL_HINTS.items():
        configured = any(os.getenv(name, "").strip() for name in env_names)
        if lane == "TradingView-style screener":
            configured = os.getenv("ROI_SNIPS_ENABLE_TRADINGVIEW_SCREENER", "").strip().lower() in {"1", "true", "yes", "on"}
        rows[lane]["configured"] = configured
        if not configured:
            rows[lane]["missing_credentials"] = env_names

    for event in events:
        lane = _lane_for_event(event)
        if not lane:
            continue
        row = rows[lane]
        row["ran"] = True
        row["produced_candidates_count"] = int(row["produced_candidates_count"]) + len(event.get("ticker_candidates") or [])
        row["produced_candidates"] = row["produced_candidates_count"]
        row["candidate_count"] = row["produced_candidates_count"]
        if event.get("official_flag") or event.get("structured_flag") or event.get("social_flag"):
            row["produced_useful_evidence_count"] = int(row["produced_useful_evidence_count"]) + 1
        tickers = {str(t).upper() for t in event.get("ticker_candidates") or []}
        if primary and primary in tickers:
            row["affected_primary_selection"] = True
            row["useful_for_primary"] = True
        if tickers and (not primary or any(ticker != primary for ticker in tickers)):
            row["affected_backup_list"] = True

    for item in errors or []:
        scout = str(item.get("scout") or item.get("source") or "").lower()
        lane = next((name for key, name in SOURCE_TO_LANE.items() if key in scout), None)
        if lane:
            rows[lane]["ran"] = True
            rows[lane]["errors"].append(str(item.get("error") or item.get("reason") or item))

    return [rows[lane] for lane in REQUIRED_SOURCE_LANES]
