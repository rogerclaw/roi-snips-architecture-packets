from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..research.query_families import generate_query_plan


PROMPT_CONTRACT = """You are Roi Snips' Broad Pro-Style Candidate Discovery module.

Date: {trading_date}
Market: U.S. equities and ETFs.
Objective: find 30-75 possible explosive short-term long candidates for today.

Do not choose the final stock.
Do not produce a safe mega-cap watchlist.
Return strict JSON with ticker, company, catalyst summary, catalyst type,
source URLs, timestamp/freshness, why it could move today, whether it may
already be too late, same-theme/beneficiary notes, and high-risk/high-upside
classification. Separate official, structured, and social evidence.
"""


def build_broad_ai_discovery_prompt(trading_date: str, query_plan: list[dict[str, Any]]) -> str:
    query_lines = "\n".join(f"- [{row.get('family')}] {row.get('query')}" for row in query_plan)
    return PROMPT_CONTRACT.format(trading_date=trading_date) + "\nQuery plan:\n" + query_lines + "\n"


def build_broad_ai_candidates(
    raw_candidates: list[dict[str, Any]],
    *,
    trading_date: str,
    status: str = "deterministic_seeded",
    failure_reason: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create the pre-filter AI-discovery artifact contract.

    This function does not claim a premium model ran. It produces the strict
    candidate contract from deterministic raw discovery so downstream enrichment
    can prove broad discovery happened or record a clean failure reason.
    """

    now = datetime.now(timezone.utc).isoformat()
    candidates: list[dict[str, Any]] = []
    for row in raw_candidates[:75]:
        candidates.append(
            {
                "ticker": row.get("ticker"),
                "company": row.get("company"),
                "catalyst_summary": row.get("raw_catalyst"),
                "catalyst_type": row.get("raw_reason"),
                "source_urls": row.get("source_urls") or ([row.get("raw_source_url")] if row.get("raw_source_url") else []),
                "timestamp_freshness": row.get("first_seen_at_utc"),
                "why_it_could_move_today": row.get("raw_catalyst") or row.get("raw_reason"),
                "may_already_be_too_late": "LATE_DISCOVERY" if abs(float(row.get("gap_pct") or 0.0)) >= 40 else None,
                "same_theme_laggard_or_direct_beneficiary": "unknown_until_enrichment",
                "high_risk_high_upside": True,
                "evidence_split": {
                    "official": "official_catalyst" in (row.get("pre_filter_flags") or []),
                    "structured": "structured_catalyst" in (row.get("pre_filter_flags") or []),
                    "social": "social_velocity" in (row.get("pre_filter_flags") or []),
                },
                "discovery_status": status,
                "failure_reason": failure_reason,
            }
        )
    if not candidates and failure_reason:
        candidates.append(
            {
                "ticker": None,
                "company": None,
                "catalyst_summary": None,
                "catalyst_type": None,
                "source_urls": [],
                "timestamp_freshness": now,
                "why_it_could_move_today": None,
                "may_already_be_too_late": None,
                "same_theme_laggard_or_direct_beneficiary": None,
                "high_risk_high_upside": False,
                "evidence_split": {"official": False, "structured": False, "social": False},
                "discovery_status": "failed",
                "failure_reason": failure_reason,
            }
        )
    query_plan = generate_query_plan([str(row.get("ticker")) for row in raw_candidates[:10] if row.get("ticker")])
    sources = [
        {
            "generated_at_utc": now,
            "trading_date": trading_date,
            "family": row.get("family"),
            "query": row.get("query"),
            "ticker": row.get("ticker"),
            "extraction_status": "planned",
            "discovery_status": status,
        }
        for row in query_plan
    ]
    return candidates, sources
