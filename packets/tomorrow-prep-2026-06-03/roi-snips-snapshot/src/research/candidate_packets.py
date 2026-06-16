from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .archetypes.policy_theme_runner import score_policy_theme_runner_archetype
from .models import MarketOverlay
from .sec_materiality import analyze_sec_materiality


def _overlay_dict(overlays: dict[str, MarketOverlay] | dict[str, dict[str, Any]], ticker: str) -> dict[str, Any]:
    overlay = overlays.get(ticker)
    if overlay is None:
        return {}
    if hasattr(overlay, "to_dict"):
        return overlay.to_dict()
    return overlay if isinstance(overlay, dict) else {}


def _evidence_rows(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in cluster.get("events") or []:
        key = str(event.get("source_url") or "").strip() or "|".join(
            [
                str(event.get("source_name") or "").strip(),
                str(event.get("headline") or "").strip(),
                str(event.get("published_at") or event.get("discovered_at") or "").strip(),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source_name": event.get("source_name"),
                "source_tier": event.get("source_tier"),
                "source_url": event.get("source_url"),
                "published_at": event.get("published_at"),
                "discovered_at": event.get("discovered_at"),
                "catalyst_type": event.get("catalyst_type"),
                "headline": event.get("headline"),
                "official_flag": bool(event.get("official_flag")),
                "structured_flag": bool(event.get("structured_flag")),
                "social_flag": bool(event.get("social_flag")),
                "credibility_score_initial": event.get("credibility_score_initial"),
                "notes": event.get("notes") or [],
            }
        )
    rows.sort(key=lambda row: (str(row.get("published_at") or row.get("discovered_at") or ""), str(row.get("source_name") or "")))
    return rows


def _source_confidence(scorecard: dict[str, Any]) -> str:
    status = str(scorecard.get("validation_status") or "")
    official = int(scorecard.get("official_confirmation_count") or 0)
    structured = int(scorecard.get("structured_confirmation_count") or 0)
    social = int(scorecard.get("social_confirmation_count") or 0)
    if status == "primary_and_structured_confirmed":
        return "high"
    if official or structured >= 2:
        return "medium_high"
    if structured:
        return "medium"
    if social:
        return "discovery_only"
    return "low"


def _why_asymmetric(row: dict[str, Any], overlay: dict[str, Any]) -> list[str]:
    scorecard = row.get("research_scorecard") or {}
    cluster = row.get("cluster") or {}
    reasons: list[str] = []
    if float(scorecard.get("freshness_score") or 0.0) >= 8.0:
        reasons.append("Fresh same-day or near-same-day catalyst.")
    if float(scorecard.get("attention_acceleration_score") or 0.0) >= 6.5:
        reasons.append("Attention velocity is high enough to support a momentum chase if corroborated.")
    if cluster.get("catalyst_type_primary") == "government_contract":
        reasons.append("Government funding/contract catalysts can create a simple high-beta narrative.")
    if float(scorecard.get("asymmetry_score") or 0.0) >= 7.0:
        reasons.append("Asymmetry score is elevated versus the ranked universe.")
    if overlay.get("premarket_dollar_volume") and float(overlay.get("premarket_dollar_volume") or 0.0) >= 1_000_000:
        reasons.append("Premarket dollar volume is large enough to show real tape confirmation.")
    return reasons or ["No clear asymmetry reason recorded; treat as lower confidence."]


def _why_may_be_wrong(row: dict[str, Any], overlay: dict[str, Any]) -> list[str]:
    scorecard = row.get("research_scorecard") or {}
    risks: list[str] = []
    if scorecard.get("validation_status") in {"social_discovery_only", "unvalidated"}:
        risks.append("Thesis is not validated by primary or structured sources.")
    if float(scorecard.get("crowding_score") or 0.0) >= 7.0:
        risks.append("Setup may already be crowded or late.")
    if overlay.get("estimated_spread_pct") is None:
        risks.append("Spread estimate is missing.")
    elif float(overlay.get("estimated_spread_pct") or 0.0) > 0.75:
        risks.append("Spread is wide enough to damage open-entry risk/reward.")
    if overlay.get("gap_pct") is not None and float(overlay.get("gap_pct") or 0.0) >= 25.0:
        risks.append("Large premarket gap may already price in the catalyst.")
    if not risks:
        risks.append("Catalyst can fail if price loses VWAP/opening range or sector momentum reverses.")
    return risks


def _invalidation_checklist(row: dict[str, Any], overlay: dict[str, Any]) -> list[str]:
    checklist = [
        "Primary/structured evidence contradicts or weakens the headline thesis.",
        "Price loses VWAP/opening range and cannot reclaim quickly.",
        "Volume fades while spread widens.",
        "Related sector basket reverses hard.",
    ]
    blockers = ((row.get("execution_gate") or {}).get("blockers") or []) + (overlay.get("execution_blockers") or [])
    for blocker in blockers:
        checklist.append(f"Deterministic gate blocker remains active: {blocker}.")
    return checklist


def build_candidate_research_packets(
    ranked: list[dict[str, Any]],
    overlays: dict[str, MarketOverlay] | dict[str, dict[str, Any]],
    *,
    top_n: int = 8,
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for row in ranked[: max(1, int(top_n))]:
        ticker = str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).upper()
        if not ticker:
            continue
        cluster = row.get("cluster") or {}
        scorecard = row.get("research_scorecard") or {}
        overlay = _overlay_dict(overlays, ticker)
        evidence = _evidence_rows(cluster)
        sec_materiality = [analyze_sec_materiality(event) for event in cluster.get("events") or [] if "sec" in f"{event.get('source_name') or ''} {event.get('source_url') or ''}".lower()]
        cluster_obj = SimpleNamespace(
            primary_ticker=ticker,
            claim_summary=cluster.get("claim_summary"),
            catalyst_type_primary=cluster.get("catalyst_type_primary"),
            catalyst_types_all=cluster.get("catalyst_types_all") or [],
            events=cluster.get("events") or [],
            social_confirmation_count=scorecard.get("social_confirmation_count") or 0,
            structured_confirmation_count=scorecard.get("structured_confirmation_count") or 0,
            official_confirmation_count=scorecard.get("official_confirmation_count") or 0,
            social_sources=cluster.get("social_sources") or [],
            structured_sources=cluster.get("structured_sources") or [],
            official_sources=cluster.get("official_sources") or [],
            obscure_confirmation_count=len(cluster.get("obscure_sources") or []),
            obscure_sources=cluster.get("obscure_sources") or [],
            attention_acceleration_score=scorecard.get("attention_acceleration_score") or 0.0,
            asymmetry_score=scorecard.get("asymmetry_score") or 0.0,
            crowdedness_preliminary=scorecard.get("crowding_score") or 0.0,
        )
        infq_archetype = score_policy_theme_runner_archetype(cluster_obj, overlay)
        packet = {
            "ticker": ticker,
            "company_name": cluster.get("company_name"),
            "headline_thesis": cluster.get("claim_summary"),
            "catalyst_summary": cluster.get("claim_summary"),
            "catalyst_type": cluster.get("catalyst_type_primary"),
            "official_sources": cluster.get("official_sources") or [],
            "structured_sources": cluster.get("structured_sources") or [],
            "social_sources": cluster.get("social_sources") or [],
            "source_lane_status_refs": row.get("source_lane_status_refs") or [],
            "first_seen_at_utc": cluster.get("first_seen_at"),
            "first_seen_price": row.get("first_seen_price"),
            "first_seen_gap_pct": row.get("first_seen_gap_pct"),
            "current_price": overlay.get("last_premarket_price"),
            "current_gap_pct": overlay.get("gap_pct"),
            "move_since_first_seen_pct": row.get("move_since_first_seen_pct"),
            "first_seen_stage": row.get("first_seen_stage"),
            "catalyst_freshness_score": scorecard.get("freshness_score"),
            "direct_beneficiary_score": infq_archetype.get("components", {}).get("direct_beneficiary_score"),
            "theme_wave_score": infq_archetype.get("policy_theme_runner_score"),
            "social_attention_velocity": scorecard.get("attention_acceleration_score"),
            "premarket_repricing_score": overlay.get("gap_pct"),
            "anti_chase_state": overlay.get("anti_chase_state"),
            "opportunity_lifecycle_state": overlay.get("opportunity_lifecycle_state"),
            "entry_viability_score": overlay.get("entry_viability_score"),
            "research_quality_score": row.get("research_priority_score"),
            "hyper_trade_score": row.get("hyper_trade_score"),
            "policy_theme_runner_score": infq_archetype.get("policy_theme_runner_score"),
            "same_style_backup_eligible": ticker not in {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"},
            "mega_cap_default_flag": ticker in {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"},
            "current_buyability_summary": {
                "anti_chase_state": overlay.get("anti_chase_state"),
                "entry_viability_score": overlay.get("entry_viability_score"),
                "gate_passed": (row.get("execution_gate") or {}).get("passed", overlay.get("tradeability_gate_pass", False)),
            },
            "validation_status": scorecard.get("validation_status", "unvalidated"),
            "source_confidence": _source_confidence(scorecard),
            "timeline": {
                "first_seen_at": cluster.get("first_seen_at"),
                "latest_update_at": cluster.get("latest_update_at"),
                "evidence_count": len(evidence),
            },
            "evidence_table": evidence,
            "market_snapshot": {
                "observed_at": overlay.get("observed_at"),
                "prior_close": overlay.get("prior_close"),
                "last_premarket_price": overlay.get("last_premarket_price"),
                "gap_pct": overlay.get("gap_pct"),
                "premarket_volume": overlay.get("premarket_volume"),
                "premarket_dollar_volume": overlay.get("premarket_dollar_volume"),
                "average_20d_dollar_volume": overlay.get("average_20d_dollar_volume"),
                "estimated_spread_pct": overlay.get("estimated_spread_pct"),
                "market_cap": overlay.get("market_cap"),
                "price_band": overlay.get("price_band"),
            },
            "infq_archetype": infq_archetype,
            "sec_materiality": sec_materiality,
            "scorecard": {
                "research_priority_score": row.get("research_priority_score"),
                "hyper_trade_score": row.get("hyper_trade_score"),
                "catalyst_strength_score": scorecard.get("catalyst_strength_score"),
                "freshness_score": scorecard.get("freshness_score"),
                "attention_acceleration_score": scorecard.get("attention_acceleration_score"),
                "crowding_score": scorecard.get("crowding_score"),
                "asymmetry_score": scorecard.get("asymmetry_score"),
                "story_stage": row.get("story_stage") or scorecard.get("story_stage"),
                "lane_tags": row.get("lane_tags") or scorecard.get("lane_tags") or [],
                "notes": scorecard.get("notes") or [],
            },
            "mega_cap_fallback_audit": row.get("mega_cap_fallback_audit") or {},
            "why_asymmetric": _why_asymmetric(row, overlay),
            "why_it_may_be_wrong": _why_may_be_wrong(row, overlay),
            "invalidation_checklist": _invalidation_checklist(row, overlay),
            "deterministic_trade_gate_status": {
                "passed": (row.get("execution_gate") or {}).get("passed", overlay.get("tradeability_gate_pass", False)),
                "execution_readiness_score": (row.get("execution_gate") or {}).get("execution_readiness_score", overlay.get("execution_readiness_score")),
                "blockers": (row.get("execution_gate") or {}).get("blockers", overlay.get("execution_blockers", [])),
                "warnings": (row.get("execution_gate") or {}).get("warnings", overlay.get("execution_warnings", [])),
            },
        }
        packets.append(packet)
    return packets
