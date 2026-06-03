from __future__ import annotations

from typing import Any

from .hyper_trade_score import score_hyper_trade
from .models import CandidateCluster, ResearchScorecard


MEGACAP_PENALTY_TICKERS = {
    "AAPL",
    "AMZN",
    "AMD",
    "GOOG",
    "GOOGL",
    "META",
    "MSFT",
    "NFLX",
    "NVDA",
    "PLTR",
    "QQQ",
    "SMCI",
    "SPY",
    "TSLA",
}


def _is_exceptional_megacap_candidate(scorecard: ResearchScorecard) -> bool:
    tags = set(scorecard.lane_tags or [])
    return (
        scorecard.catalyst_strength_score >= 8.5
        and scorecard.hyper_trade_score >= 8.5
        and scorecard.attention_acceleration_score >= 7.5
        and bool(tags.intersection({"OPENING_BURST_HYPER_LONG", "VERIFIED_CATALYST_RUNNER", "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE"}))
    )


def _mega_cap_fallback_audit(cluster: CandidateCluster, scorecard: ResearchScorecard) -> dict[str, Any]:
    is_mega = cluster.primary_ticker in MEGACAP_PENALTY_TICKERS
    exceptional = _is_exceptional_megacap_candidate(scorecard) if is_mega else False
    return {
        "is_common_mega_cap_fallback": is_mega,
        "demote_unless_exceptional": bool(is_mega and not exceptional),
        "exceptional_catalyst_required": is_mega,
        "passed_exceptional_catalyst_test": exceptional,
        "requires_small_mid_cap_comparison": is_mega,
        "reason": "not_mega_cap" if not is_mega else ("exceptional_catalyst_and_tape_profile" if exceptional else "generic_or_nonexceptional_mega_cap_fallback"),
    }


def _story_stage(cluster: CandidateCluster) -> str:
    if float(cluster.story_stage_score or 0.0) <= 3.0:
        return "exhausted"
    if cluster.crowdedness_preliminary >= 8.0:
        return "crowded"
    if cluster.freshness_score >= 8.0 and cluster.attention_acceleration_score <= 4.5:
        return "early"
    if cluster.freshness_score >= 5.0:
        return "developing"
    return "late"


def _evidence_diversity(official: float, structured: float, social: float, obscure: float) -> float:
    lanes = 0
    lanes += 1 if official > 0 else 0
    lanes += 1 if structured > 0 else 0
    lanes += 1 if social > 0 else 0
    lanes += 1 if obscure > 0 else 0
    if lanes <= 1:
        return 2.5
    if lanes == 2:
        return 5.8
    if lanes == 3:
        return 7.8
    return 9.0


def _obscurity_bonus(cluster: CandidateCluster) -> float:
    bonus = 0.0
    obscure = float(cluster.obscure_confirmation_count or len(cluster.obscure_sources))
    if obscure:
        bonus += min(1.2, obscure * 0.45)
    headline = str(cluster.claim_summary or "").lower()
    if "obscure catalyst candidate" in headline:
        bonus += 0.25
    if cluster.primary_ticker in MEGACAP_PENALTY_TICKERS:
        bonus -= 1.1
        if cluster.official_confirmation_count and cluster.structured_confirmation_count and cluster.catalyst_strength_score >= 5.8:
            bonus += 0.55
    return bonus


def _social_only_penalty(official: float, structured: float, social: float, crowding: float) -> float:
    if official == 0 and structured == 0 and social > 0:
        return 1.2 + min(0.8, crowding * 0.08)
    return 0.0


def _validation_status(official: float, structured: float, social: float) -> str:
    if official > 0 and structured > 0:
        return "primary_and_structured_confirmed"
    if official > 0:
        return "primary_confirmed"
    if structured > 0:
        return "structured_confirmed"
    if social > 0:
        return "social_discovery_only"
    return "unvalidated"


def _hard_catalyst_bonus(cluster: CandidateCluster) -> float:
    text = " ".join([str(cluster.claim_summary or ""), *[str(e.get("headline") or "") for e in cluster.events], *[str(e.get("raw_text") or "") for e in cluster.events]]).lower()
    catalyst_types = {str(cluster.catalyst_type_primary or ""), *[str(t) for t in (cluster.catalyst_types_all or [])]}
    bonus = 0.0
    if "government_contract" in catalyst_types:
        bonus += 0.55
        if any(token in text for token in ["chips", "department of commerce", "commerce department", "letter of intent", "loi", "grant", "funding", "government equity", "equity stake", "quantum"]):
            bonus += 0.65
    if any(token in text for token in ["same-day investor", "symposium", "fireside chat", "presents today", "conference today"]):
        bonus += 0.35
    return min(1.55, bonus)


def score_cluster_for_research(cluster: CandidateCluster) -> ResearchScorecard:
    official = float(cluster.official_confirmation_count or len(cluster.official_sources))
    structured = float(cluster.structured_confirmation_count or len(cluster.structured_sources))
    social = float(cluster.social_confirmation_count or len(cluster.social_sources))
    obscure = float(cluster.obscure_confirmation_count or len(cluster.obscure_sources))
    catalyst = float(cluster.catalyst_strength_score or 0.0)
    freshness = float(cluster.freshness_score or 0.0)
    attention = float(cluster.attention_acceleration_score or 0.0)
    asymmetry = float(cluster.asymmetry_score or 0.0)
    crowding = float(cluster.crowdedness_preliminary or 0.0)
    diversity = _evidence_diversity(official, structured, social, obscure)
    source_quality = float(cluster.source_quality_score or 0.0)
    obscurity_bias = _obscurity_bonus(cluster)
    social_only_penalty = _social_only_penalty(official, structured, social, crowding)
    hard_catalyst_bonus = _hard_catalyst_bonus(cluster)
    legacy_priority = (
        catalyst * 0.29
        + freshness * 0.19
        + attention * 0.13
        + asymmetry * 0.14
        + min(10.0, official * 2.0 + structured * 1.25) * 0.12
        + diversity * 0.08
        + source_quality * 0.08
        + obscurity_bias
        + hard_catalyst_bonus
        - crowding * 0.11
        - social_only_penalty
    )
    stage = _story_stage(cluster)
    if stage == "early":
        legacy_priority += 0.95
    elif stage == "crowded":
        legacy_priority -= 1.0
    elif stage == "exhausted":
        legacy_priority -= 1.6

    hyper = score_hyper_trade(cluster)
    priority = (hyper["hyper_trade_score"] * 0.68) + (max(0.0, min(legacy_priority, 10.0)) * 0.32)

    notes: list[str] = []
    if official:
        notes.append(f"official_confirmations={int(official)}")
    if structured:
        notes.append(f"structured_confirmations={int(structured)}")
    if social:
        notes.append(f"social_confirmations={int(social)}")
    if obscure:
        notes.append(f"obscure_confirmations={int(obscure)}")
    notes.append(f"evidence_diversity={round(diversity, 2)}")
    if cluster.primary_ticker in MEGACAP_PENALTY_TICKERS:
        notes.append("megacap_penalty_applied")
    if social_only_penalty:
        notes.append("social_only_penalty_applied")
    if hard_catalyst_bonus:
        notes.append(f"hard_catalyst_bonus={round(hard_catalyst_bonus, 3)}")
    validation_status = _validation_status(official, structured, social)
    notes.append(f"validation_status={validation_status}")
    notes.append(f"story_stage={stage}")
    notes.append(f"legacy_research_priority={round(max(0.0, min(legacy_priority, 10.0)), 3)}")
    notes.append("primary_score=hyper_trade_score")

    penalties: list[str] = []
    components = hyper["components"]
    if components["mega_cap_boring_penalty"]:
        penalties.append("mega_cap_boring_penalty")
    if components["fake_hype_penalty"]:
        penalties.append("fake_hype_penalty")
    if components["dilution_or_offering_penalty"]:
        penalties.append("dilution_or_offering_penalty")
    if components["exhaustion_penalty"]:
        penalties.append("exhaustion_penalty")

    return ResearchScorecard(
        ticker=cluster.primary_ticker,
        catalyst_strength_score=round(catalyst, 3),
        freshness_score=round(freshness, 3),
        official_confirmation_count=int(official),
        structured_confirmation_count=int(structured),
        social_confirmation_count=int(social),
        attention_acceleration_score=round(attention, 3),
        crowding_score=round(crowding, 3),
        asymmetry_score=round(asymmetry, 3),
        research_priority_score=round(max(0.0, min(priority, 10.0)), 3),
        story_stage=stage,
        notes=notes,
        hyper_trade_score=hyper["hyper_trade_score"],
        lane_tags=hyper["lane_tags"],
        speculative_risk_penalties=penalties,
        validation_status=validation_status,
    )


def rank_clusters_for_research(clusters: list[CandidateCluster]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for cluster in clusters:
        scorecard = score_cluster_for_research(cluster)
        audit = _mega_cap_fallback_audit(cluster, scorecard)
        research_priority_score = scorecard.research_priority_score
        hyper_trade_score = scorecard.hyper_trade_score
        if audit["demote_unless_exceptional"]:
            research_priority_score = round(max(0.0, research_priority_score - 1.5), 3)
            hyper_trade_score = round(max(0.0, hyper_trade_score - 1.2), 3)
            scorecard.research_priority_score = research_priority_score
            scorecard.hyper_trade_score = hyper_trade_score
            scorecard.notes.append("megacap_fallback_audit=demoted_nonexceptional")
        elif audit["passed_exceptional_catalyst_test"]:
            scorecard.notes.append("megacap_fallback_audit=passed_exceptional")
        ranked.append(
            {
                "ticker": cluster.primary_ticker,
                "cluster": cluster.to_dict(),
                "research_scorecard": scorecard.to_dict(),
                "research_priority_score": research_priority_score,
                "hyper_trade_score": hyper_trade_score,
                "lane_tags": scorecard.lane_tags,
                "story_stage": scorecard.story_stage,
                "mega_cap_fallback_audit": audit,
            }
        )
    ranked.sort(
        key=lambda row: (
            row["hyper_trade_score"],
            row["research_priority_score"],
            row["research_scorecard"]["catalyst_strength_score"],
            row["research_scorecard"]["asymmetry_score"],
            row["research_scorecard"]["freshness_score"],
        ),
        reverse=True,
    )
    return ranked
