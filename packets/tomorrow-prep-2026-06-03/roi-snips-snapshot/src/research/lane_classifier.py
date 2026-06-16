from __future__ import annotations

from typing import Any

from .models import CandidateCluster, MarketOverlay


def _social_attention_extreme(cluster: CandidateCluster) -> bool:
    social = int(cluster.social_confirmation_count or len(cluster.social_sources))
    attention = float(cluster.attention_acceleration_score or 0.0)
    return social >= 3 or attention >= 8.0


def _tape_repricing_strong(overlay: MarketOverlay | None) -> bool:
    if overlay is None:
        return False
    gap = float(overlay.gap_pct or 0.0)
    dollar_volume = float(overlay.premarket_dollar_volume or 0.0)
    readiness = float(overlay.execution_readiness_score or 0.0)
    return gap >= 8.0 and dollar_volume >= 1_000_000 and readiness >= 55.0


def classify_candidate_lanes(cluster: CandidateCluster, overlay: MarketOverlay | None = None) -> list[str]:
    lanes: list[str] = []
    catalyst = str(cluster.catalyst_type_primary or "").lower()
    official_or_structured = bool(cluster.official_sources or cluster.structured_sources)

    if official_or_structured and float(cluster.catalyst_strength_score or 0.0) >= 4.5:
        lanes.append("VERIFIED_CATALYST_RUNNER")

    if _social_attention_extreme(cluster) and (_tape_repricing_strong(overlay) or overlay is None):
        lanes.append("SOCIAL_TAPE_ROCKET")

    if overlay is not None:
        gap = float(overlay.gap_pct or 0.0)
        premarket_dollar_volume = float(overlay.premarket_dollar_volume or 0.0)
        if abs(gap) >= 6.0 or premarket_dollar_volume >= 1_000_000:
            lanes.append("MOVER_FIRST_EXPLAIN_LATER")
    elif any(key in catalyst for key in ["exchange", "mover", "social", "obscure"]):
        lanes.append("MOVER_FIRST_EXPLAIN_LATER")

    if not lanes:
        lanes.append("VERIFIED_CATALYST_RUNNER" if official_or_structured else "MOVER_FIRST_EXPLAIN_LATER")

    return sorted(set(lanes))


def lane_summary(cluster: CandidateCluster, overlay: MarketOverlay | None = None) -> dict[str, Any]:
    return {
        "lane_tags": classify_candidate_lanes(cluster, overlay),
        "social_attention_extreme": _social_attention_extreme(cluster),
        "tape_repricing_strong": _tape_repricing_strong(overlay),
    }
