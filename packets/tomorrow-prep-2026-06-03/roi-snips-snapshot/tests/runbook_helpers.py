from __future__ import annotations

from datetime import datetime, timezone


def event(
    ticker: str = "INFQ",
    *,
    source_name: str = "sec_edgar",
    headline: str = "INFQ wins government quantum funding award",
    catalyst_type: str = "government_contract",
    official: bool = True,
    structured: bool = False,
    social: bool = False,
    url: str = "https://sec.gov/infq",
    discovered_at: str = "2026-05-27T12:05:00+00:00",
) -> dict:
    return {
        "event_id": f"{source_name}-{ticker}",
        "source_name": source_name,
        "source_tier": 1,
        "source_url": url,
        "discovered_at": discovered_at,
        "published_at": discovered_at,
        "updated_at": None,
        "headline": headline,
        "raw_text": headline,
        "company_name": f"{ticker} Holdings",
        "ticker_candidates": [ticker],
        "catalyst_type": catalyst_type,
        "official_flag": official,
        "structured_flag": structured,
        "social_flag": social,
        "credibility_score_initial": 8.0,
        "freshness_hours": 0.5,
        "extraction_confidence": 0.9,
        "notes": [],
    }


def ranked_row(symbol: str = "INFQ", *, gap_pct: float = 18.0, hyper: float = 8.8, lanes: list[str] | None = None) -> dict:
    lanes = lanes or ["INFQ_STYLE_GOVERNMENT_SECTOR_WAVE", "POLICY_THEME_RUNNER_ARCHETYPE"]
    return {
        "ticker": symbol,
        "cluster": {
            "primary_ticker": symbol,
            "company_name": f"{symbol} Holdings",
            "claim_summary": f"{symbol} fresh government contract catalyst",
            "catalyst_type_primary": "government_contract",
            "catalyst_types_all": ["government_contract"],
            "first_seen_at": "2026-05-27T12:05:00+00:00",
            "latest_update_at": "2026-05-27T12:10:00+00:00",
            "official_sources": ["SEC EDGAR"],
            "structured_sources": ["Benzinga"],
            "social_sources": ["Grok/X"],
            "obscure_sources": [],
            "events": [
                event(symbol, source_name="sec_edgar", official=True, structured=False, social=False),
                event(symbol, source_name="benzinga", official=False, structured=True, social=False, url="https://benzinga.com/infq"),
            ],
        },
        "research_scorecard": {
            "catalyst_strength_score": 9.0,
            "freshness_score": 9.0,
            "official_confirmation_count": 1,
            "structured_confirmation_count": 1,
            "social_confirmation_count": 1,
            "attention_acceleration_score": 7.5,
            "crowding_score": 4.0,
            "asymmetry_score": 8.0,
            "research_priority_score": 8.6,
            "hyper_trade_score": hyper,
            "story_stage": "early",
            "lane_tags": lanes,
            "notes": [],
            "validation_status": "primary_and_structured_confirmed",
        },
        "research_priority_score": 8.6,
        "hyper_trade_score": hyper,
        "story_stage": "early",
        "lane_tags": lanes,
        "overlay": overlay(symbol, gap_pct=gap_pct),
    }


def overlay(symbol: str = "INFQ", *, gap_pct: float = 18.0) -> dict:
    return {
        "ticker": symbol,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "prior_close": 10.0,
        "last_premarket_price": 10.0 * (1 + gap_pct / 100),
        "gap_pct": gap_pct,
        "premarket_volume": 500_000,
        "premarket_dollar_volume": 5_900_000,
        "average_20d_dollar_volume": 35_000_000,
        "estimated_spread_pct": 0.25,
        "halt_status": "NONE",
        "market_cap": 450_000_000,
        "price_band": "5_to_20",
        "tradeability_gate_pass": True,
        "tradeability_notes": [],
        "execution_readiness_score": 85,
        "execution_blockers": [],
        "execution_warnings": [],
        "anti_chase_state": "PREMARKET_BUILDING",
        "opportunity_lifecycle_state": "PREMARKET_BUILDING",
        "entry_viability_score": 72,
    }
