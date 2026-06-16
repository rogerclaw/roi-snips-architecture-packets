from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .trade_authorization_ticket import BLOCKED_DEFAULT_MEGACAPS


def _score(candidate: dict[str, Any], x_by_ticker: dict[str, dict[str, Any]], prior_winners: set[str]) -> float:
    ticker = str(candidate.get("ticker") or "").upper()
    x = x_by_ticker.get(ticker) or {}
    score = 0.0
    score += 20 if candidate.get("verified_catalyst") else -30
    score += float(candidate.get("direct_beneficiary_score") or 0) * 4
    score += float(x.get("attention_velocity_score") or 0) * 3
    score -= float(candidate.get("stale_news_risk") or 0) * 2
    score -= float(candidate.get("dilution_or_offering_risk") or 0) * 2
    score -= float(candidate.get("already_priced_in_risk") or 0)
    if ticker in BLOCKED_DEFAULT_MEGACAPS:
        score -= 25
    if ticker in prior_winners:
        score -= 20
    return round(score, 3)


def run_grok_d_research_tournament(
    *,
    seed_packet: dict[str, Any],
    x_heat_radar: dict[str, Any],
    web_verification: dict[str, Any],
    market_overlays: dict[str, Any] | None = None,
    source_lane_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prior_winners = {str((row or {}).get("ticker") or (row or {}).get("symbol") or "").upper() for row in seed_packet.get("prior_winners") or []}
    if x_heat_radar.get("status") == "failed":
        return _no_trade("x_search_failed_or_unavailable")
    if web_verification.get("status") == "failed":
        return _no_trade("web_search_failed_or_unavailable")
    x_by_ticker = {str(row.get("ticker") or "").upper(): row for row in x_heat_radar.get("candidates") or []}
    verified = list(web_verification.get("verified_candidates") or [])
    scored = [{**row, "_score": _score(row, x_by_ticker, prior_winners)} for row in verified]
    scored.sort(key=lambda row: row["_score"], reverse=True)
    if not scored:
        return _no_trade("no_verified_candidates")
    leader = scored[0]
    ticker = str(leader.get("ticker") or "").upper()
    if not leader.get("verified_catalyst"):
        return _no_trade("x_hype_without_hard_verification")
    if ticker in BLOCKED_DEFAULT_MEGACAPS and leader["_score"] < 35:
        return _no_trade("mega_cap_default_without_exceptional_evidence")
    if ticker in prior_winners and leader["_score"] < 35:
        return _no_trade("stale_prior_winner_without_fresh_exception")
    x = x_by_ticker.get(ticker) or {}
    return {
        "stage": "grok_candidate_discovery_tournament",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "RECOMMEND_FOR_DEEP_MINI_REVIEW",
        "grok_research_only": True,
        "can_authorize_live_trade": False,
        "research_leader": ticker,
        "authorized_candidate": {
            "ticker": ticker,
            "company": leader.get("company"),
            "catalyst": leader.get("verification_summary") or "Verified current catalyst",
            "why_it_can_move": x.get("why_it_may_matter_at_open") or "Hard catalyst plus social attention can pull opening liquidity.",
            "why_not_fully_priced": "Requires live tape confirmation; research does not assume the move is already safe.",
            "evidence_split": {
                "official": leader.get("official_sources") or [],
                "structured": leader.get("structured_sources") or [],
                "social": sorted(set([*(leader.get("social_sources") or []), *(x.get("key_threads") or [])])),
                "market_data": list((market_overlays or {}).get(ticker, {}).get("sources") or []),
            },
            "x_narrative_summary": x.get("narrative") or "",
            "premarket_behavior": (market_overlays or {}).get(ticker, {}).get("summary") or "Requires fresh candidate-specific market data before entry.",
            "technical_plan": "Wait for opening burst, ORB, VWAP reclaim, or event-timed confirmation; no blind entry from research.",
            "strategy": "OPENING_BURST_HYPER_LONG",
            "buy_range_or_wait_trigger": "Wait for deterministic live tape confirmation.",
            "same_day_target": "Use live tape-defined target; research target is not an order.",
            "one_to_three_day_target": "Use catalyst follow-through only if position manager allows.",
            "thesis_break": "Catalyst disproven, spread/liquidity fails, or opening tape rejects.",
            "sell_triggers": ["profit spike into exhaustion", "VWAP loss after failed reclaim", "fresh dilution/offering headline"],
            "must_not_trade_if": ["ticket invalid", "final readiness not GREEN", "market data stale", "spread/liquidity guard fails"],
        },
        "research_only_backups": [row.get("ticker") for row in scored[1:6] if row.get("ticker")],
        "names_for_deep_mini_to_judge": [row.get("ticker") for row in scored[:10] if row.get("ticker")],
        "mega_cap_defaults_rejected": [row.get("ticker") for row in scored if str(row.get("ticker") or "").upper() in BLOCKED_DEFAULT_MEGACAPS and row.get("ticker") != ticker],
        "stale_prior_winners_rejected": [row.get("ticker") for row in scored if str(row.get("ticker") or "").upper() in prior_winners and row.get("ticker") != ticker],
        "source_lane_status": source_lane_status or [],
        "no_trade_reason": None,
    }


def run_grok_red_team(tournament: dict[str, Any]) -> dict[str, Any]:
    candidate = tournament.get("authorized_candidate") or {}
    ticker = str(candidate.get("ticker") or "").upper()
    fatal = []
    risks = []
    evidence = candidate.get("evidence_split") or {}
    if tournament.get("decision") not in {"AUTHORIZE_ONE", "RECOMMEND_FOR_DEEP_MINI_REVIEW"}:
        fatal.append(tournament.get("no_trade_reason") or "no_authorized_candidate")
    if not ticker:
        fatal.append("missing_ticker")
    if not (evidence.get("official") or evidence.get("structured")):
        fatal.append("no_hard_source_verification")
    if not evidence.get("social"):
        risks.append("weak_x_social_confirmation")
    if ticker in BLOCKED_DEFAULT_MEGACAPS and not tournament.get("mega_cap_exception"):
        risks.append("mega_cap_requires_explicit_exception")
    verdict = "FAIL_NO_TRADE" if fatal else ("PASS_ONLY_WITH_TAPE" if risks else "PASS")
    return {
        "stage": "grok_challenger_notes",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "fatal_flaws": fatal,
        "nonfatal_risks": risks,
        "required_live_confirmations": ["fresh quote/trade data", "spread guard", "strategy-specific tape predicate", "final arming gate GREEN"],
        "should_block_ticket": bool(fatal),
        "grok_research_only": True,
        "can_authorize_live_trade": False,
        "reason": "; ".join(fatal or risks or ["candidate passes research red team; execution still requires live tape"]),
    }


def _no_trade(reason: str) -> dict[str, Any]:
    return {
        "stage": "grok_candidate_discovery_tournament",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "NO_TRADE",
        "grok_research_only": True,
        "can_authorize_live_trade": False,
        "research_leader": None,
        "authorized_candidate": None,
        "research_only_backups": [],
        "mega_cap_defaults_rejected": [],
        "stale_prior_winners_rejected": [],
        "no_trade_reason": reason,
    }
