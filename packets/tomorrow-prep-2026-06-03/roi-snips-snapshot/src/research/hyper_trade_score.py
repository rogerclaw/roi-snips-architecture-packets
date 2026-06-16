from __future__ import annotations

from typing import Any

from .archetypes.policy_theme_runner import score_policy_theme_runner_archetype
from .lane_classifier import classify_candidate_lanes
from .models import CandidateCluster, MarketOverlay
from .sec_materiality import analyze_sec_materiality


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


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def _premarket_repricing_energy(overlay: MarketOverlay | None) -> float:
    if overlay is None:
        return 0.0
    gap = abs(float(overlay.gap_pct or 0.0))
    dollar_volume = float(overlay.premarket_dollar_volume or 0.0)
    spread_pct = overlay.estimated_spread_pct
    score = min(4.0, gap / 4.0)
    if dollar_volume >= 10_000_000:
        score += 3.0
    elif dollar_volume >= 3_000_000:
        score += 2.2
    elif dollar_volume >= 1_000_000:
        score += 1.4
    if spread_pct is not None and spread_pct <= 0.5:
        score += 1.4
    if float(overlay.execution_readiness_score or 0.0) >= 70.0:
        score += 1.2
    return _clamp(score)


def _opening_drive_potential(cluster: CandidateCluster, overlay: MarketOverlay | None) -> float:
    base = float(cluster.asymmetry_score or 0.0) * 0.45 + float(cluster.attention_acceleration_score or 0.0) * 0.25
    if overlay is not None:
        if abs(float(overlay.gap_pct or 0.0)) >= 5.0:
            base += 1.5
        if float(overlay.premarket_dollar_volume or 0.0) >= 1_000_000:
            base += 1.2
        if overlay.estimated_spread_pct is not None and overlay.estimated_spread_pct <= 0.75:
            base += 0.8
    return _clamp(base)


def _earlyness_score(cluster: CandidateCluster) -> float:
    story_stage = float(cluster.story_stage_score or 0.0)
    freshness = float(cluster.freshness_score or 0.0)
    crowding = float(cluster.crowdedness_preliminary or 0.0)
    return _clamp((story_stage * 0.55) + (freshness * 0.35) - (crowding * 0.2))


def _float_squeeze_factor(cluster: CandidateCluster) -> float:
    text = " ".join([str(cluster.claim_summary or ""), *[str(e.get("headline") or "") for e in cluster.events]]).lower()
    score = 0.0
    if "low float" in text or "float" in text:
        score += 3.0
    if "squeeze" in text or "short interest" in text:
        score += 3.5
    if float(cluster.attention_acceleration_score or 0.0) >= 7.0:
        score += 2.0
    return _clamp(score)


def _level_clarity(cluster: CandidateCluster, overlay: MarketOverlay | None) -> float:
    score = float(cluster.asymmetry_score or 0.0) * 0.45
    if overlay is not None:
        if overlay.prior_close and overlay.last_premarket_price:
            score += 1.4
        if overlay.estimated_spread_pct is not None:
            score += 1.2
        if overlay.premarket_volume:
            score += 1.0
    return _clamp(score)


def _dilution_or_offering_penalty(cluster: CandidateCluster) -> float:
    text = " ".join([str(cluster.claim_summary or ""), *[str(e.get("headline") or "") for e in cluster.events]]).lower()
    penalty = 0.0
    for key in ["offering", "atm", "s-1", "s-3", "registered direct", "reverse split", "dilution"]:
        if key in text:
            penalty += 2.0
    return _clamp(penalty)


def _fake_hype_penalty(cluster: CandidateCluster) -> float:
    official_or_structured = bool(cluster.official_sources or cluster.structured_sources)
    social = int(cluster.social_confirmation_count or len(cluster.social_sources))
    if official_or_structured or social == 0:
        return 0.0
    return _clamp(7.0 + float(cluster.crowdedness_preliminary or 0.0) * 0.45)


def _generic_sec_filing_penalty(cluster: CandidateCluster) -> float:
    penalty = 0.0
    for event in cluster.events:
        source = f"{event.get('source_name') or ''} {event.get('source_url') or ''}".lower()
        if "sec" not in source and "edgar" not in source:
            continue
        penalty = max(penalty, float(analyze_sec_materiality(event).get("generic_sec_filing_penalty") or 0.0))
    return _clamp(penalty)


def hyper_trade_score_components(cluster: CandidateCluster, overlay: MarketOverlay | None = None) -> dict[str, float]:
    exhaustion = 0.0
    if float(cluster.story_stage_score or 0.0) <= 3.0:
        exhaustion += 4.0
    exhaustion += max(0.0, float(cluster.crowdedness_preliminary or 0.0) - 6.0) * 0.65
    if overlay is not None and float(overlay.gap_pct or 0.0) >= 25.0:
        exhaustion += 1.5

    mega_cap = 8.0 if cluster.primary_ticker in MEGACAP_PENALTY_TICKERS else 0.0
    if mega_cap and float(cluster.catalyst_strength_score or 0.0) >= 8.0 and float(cluster.attention_acceleration_score or 0.0) >= 7.0:
        mega_cap = 3.0

    infq = score_policy_theme_runner_archetype(cluster, overlay)
    return {
        "infq_archetype_score": round(float(infq.get("infq_archetype_score") or 0.0), 3),
        "premarket_repricing_energy": round(_premarket_repricing_energy(overlay), 3),
        "catalyst_violence": round(_clamp(float(cluster.catalyst_strength_score or 0.0)), 3),
        "opening_drive_potential": round(_opening_drive_potential(cluster, overlay), 3),
        "attention_velocity": round(_clamp(float(cluster.attention_acceleration_score or 0.0)), 3),
        "sector_wave_score": round(float((infq.get("components") or {}).get("sector_wave_score") or 0.0), 3),
        "earlyness_score": round(_earlyness_score(cluster), 3),
        "float_squeeze_factor": round(_float_squeeze_factor(cluster), 3),
        "level_clarity": round(_level_clarity(cluster, overlay), 3),
        "source_quality": round(_clamp(float(cluster.source_quality_score or 0.0)), 3),
        "exhaustion_penalty": round(_clamp(exhaustion), 3),
        "dilution_or_offering_penalty": round(_dilution_or_offering_penalty(cluster), 3),
        "fake_hype_penalty": round(_fake_hype_penalty(cluster), 3),
        "mega_cap_boring_penalty": round(mega_cap, 3),
        "generic_sec_filing_penalty": round(_generic_sec_filing_penalty(cluster), 3),
    }


def score_hyper_trade(cluster: CandidateCluster, overlay: MarketOverlay | None = None) -> dict[str, Any]:
    c = hyper_trade_score_components(cluster, overlay)
    score = (
        0.18 * c["infq_archetype_score"]
        + 0.16 * c["premarket_repricing_energy"]
        + 0.15 * c["catalyst_violence"]
        + 0.13 * c["opening_drive_potential"]
        + 0.12 * c["attention_velocity"]
        + 0.10 * c["sector_wave_score"]
        + 0.08 * c["earlyness_score"]
        + 0.05 * c["level_clarity"]
        + 0.04 * c["source_quality"]
        - 0.10 * c["exhaustion_penalty"]
        - 0.08 * c["dilution_or_offering_penalty"]
        - 0.06 * c["fake_hype_penalty"]
        - 0.10 * c["mega_cap_boring_penalty"]
        - 0.08 * c["generic_sec_filing_penalty"]
    )
    archetype = score_policy_theme_runner_archetype(cluster, overlay)
    return {
        "hyper_trade_score": round(_clamp(score), 3),
        "components": c,
        "lane_tags": sorted(set(classify_candidate_lanes(cluster, overlay) + list(archetype.get("tags") or []))),
    }
