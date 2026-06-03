from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hyper_trade_score import score_hyper_trade
from .lane_classifier import classify_candidate_lanes
from .models import CandidateCluster, ExecutionGateDecision, MarketOverlay
from .ranking import rank_clusters_for_research


@dataclass
class GateResult:
    passed: bool
    reasons: list[str]
    score: float
    hard_blockers: list[str] | None = None
    speculative_risk_penalties: list[str] | None = None


DEFAULT_THRESHOLDS = {
    "research": {
        "min_source_quality": 4.5,
        "max_candidates_after_discovery": 40,
        "max_candidates_for_verification": 15,
    },
    "execution": {
        "min_price": 3.0,
        "min_avg_dollar_volume": 10_000_000.0,
        "max_spread_pct": 0.75,
        "min_execution_readiness_score": 60.0,
        "require_official_or_structured": True,
        "allow_social_tape_rocket_without_official": True,
        "social_tape_min_hyper_score": 7.0,
        "social_tape_min_attention_score": 8.0,
        "social_tape_min_premarket_dollar_volume": 1_000_000.0,
        "hard_max_spread_pct": 2.0,
    },
}


MECHANICAL_OVERLAY_BLOCKERS = {
    "price_missing",
    "spread_estimate_missing",
    "halted",
    "quote_missing",
    "stale_quote",
    "bid_ask_missing_for_execution",
    "no_quote",
}


SPECULATIVE_OVERLAY_PENALTIES = {
    "price_below_execution_floor",
    "avg_dollar_volume_below_execution_floor",
    "average_20d_dollar_volume_missing",
    "premarket_dollar_volume_light",
    "premarket_dollar_volume_missing",
    "spread_too_wide",
}


def _thresholds(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {"research": dict(DEFAULT_THRESHOLDS["research"]), "execution": dict(DEFAULT_THRESHOLDS["execution"])}
    if not cfg:
        return merged
    if "research" in cfg or "execution" in cfg:
        merged["research"].update((cfg.get("research") or {}))
        merged["execution"].update((cfg.get("execution") or {}))
        return merged
    # backward compatibility with flat workflow thresholds
    flat = dict(cfg)
    if "min_source_quality_for_best_pick" in flat:
        merged["research"]["min_source_quality"] = flat["min_source_quality_for_best_pick"]
    if "max_candidates_for_verification" in flat:
        merged["research"]["max_candidates_for_verification"] = flat["max_candidates_for_verification"]
    if "min_price_aggressive" in flat:
        merged["execution"]["min_price"] = flat["min_price_aggressive"]
    if "min_avg_dollar_volume_aggressive" in flat:
        merged["execution"]["min_avg_dollar_volume"] = flat["min_avg_dollar_volume_aggressive"]
    if "min_tradeability_score_for_best_pick" in flat:
        merged["execution"]["min_execution_readiness_score"] = float(flat["min_tradeability_score_for_best_pick"]) * 10.0
    return merged


def evaluate_execution_gate(cluster: CandidateCluster, overlay: MarketOverlay | None = None, cfg: dict[str, Any] | None = None) -> GateResult:
    thresholds = _thresholds(cfg)
    execution_cfg = thresholds["execution"]
    reasons: list[str] = []
    hard_blockers: list[str] = []
    speculative_penalties: list[str] = []

    if not cluster.primary_ticker or len(cluster.primary_ticker) > 5:
        hard_blockers.append("ticker_invalid_or_nonstandard")

    lane_tags = classify_candidate_lanes(cluster, overlay)
    hyper = score_hyper_trade(cluster, overlay)
    social_attention = float(cluster.attention_acceleration_score or 0.0)
    premarket_dollar_volume = float((overlay.premarket_dollar_volume if overlay else 0.0) or 0.0)
    social_tape_exception = (
        execution_cfg.get("allow_social_tape_rocket_without_official", True)
        and "SOCIAL_TAPE_ROCKET" in lane_tags
        and (
            hyper["hyper_trade_score"] >= float(execution_cfg.get("social_tape_min_hyper_score", 7.0))
            or social_attention >= float(execution_cfg.get("social_tape_min_attention_score", 8.0)) + 1.0
        )
        and social_attention >= float(execution_cfg.get("social_tape_min_attention_score", 8.0))
        and overlay is not None
        and premarket_dollar_volume >= float(execution_cfg.get("social_tape_min_premarket_dollar_volume", 1_000_000.0))
    )

    if execution_cfg.get("require_official_or_structured", True) and not (cluster.official_sources or cluster.structured_sources):
        if social_tape_exception:
            speculative_penalties.append("missing_official_or_structured_confirmation_social_tape_exception")
        else:
            hard_blockers.append("missing_official_or_structured_confirmation")

    if overlay is None:
        hard_blockers.append("missing_market_overlay")
        reasons = sorted(set(hard_blockers + speculative_penalties))
        return GateResult(False, reasons, 0.0, sorted(set(hard_blockers)), sorted(set(speculative_penalties)))

    for blocker in overlay.execution_blockers:
        if blocker == "spread_too_wide":
            if overlay.estimated_spread_pct is not None and overlay.estimated_spread_pct > float(execution_cfg.get("hard_max_spread_pct", 2.0)):
                hard_blockers.append("spread_mechanically_too_wide")
            else:
                speculative_penalties.append("spread_wide_size_down")
        elif blocker in MECHANICAL_OVERLAY_BLOCKERS:
            hard_blockers.append(blocker)
        elif blocker in SPECULATIVE_OVERLAY_PENALTIES:
            speculative_penalties.append(blocker)
        else:
            hard_blockers.append(blocker)
    if overlay.last_premarket_price is not None and overlay.last_premarket_price < float(execution_cfg.get("min_price", 3.0)):
        speculative_penalties.append("price_below_execution_floor")
    if overlay.average_20d_dollar_volume is not None and overlay.average_20d_dollar_volume < float(execution_cfg.get("min_avg_dollar_volume", 10_000_000.0)):
        speculative_penalties.append("avg_dollar_volume_below_execution_floor")
    if overlay.estimated_spread_pct is not None and overlay.estimated_spread_pct > float(execution_cfg.get("max_spread_pct", 0.75)):
        if overlay.estimated_spread_pct > float(execution_cfg.get("hard_max_spread_pct", 2.0)):
            hard_blockers.append("spread_mechanically_too_wide")
        else:
            speculative_penalties.append("spread_wide_size_down")
    if overlay.execution_readiness_score < float(execution_cfg.get("min_execution_readiness_score", 60.0)):
        speculative_penalties.append("execution_readiness_below_threshold")
    if float(cluster.story_stage_score or 0.0) <= 3.0 and (overlay.gap_pct or 0.0) >= 20.0:
        speculative_penalties.append("parabolic_extension_risk")

    penalty_cost = len(set(speculative_penalties)) * 4.0
    score = max(0.0, min(100.0, overlay.execution_readiness_score + hyper["hyper_trade_score"] * 5.0 - cluster.crowdedness_preliminary * 1.5 - penalty_cost))
    reasons = sorted(set(hard_blockers + speculative_penalties))
    return GateResult(passed=not hard_blockers, reasons=reasons, score=round(score, 3), hard_blockers=sorted(set(hard_blockers)), speculative_risk_penalties=sorted(set(speculative_penalties)))


def evaluate_cluster(cluster: CandidateCluster, overlay: MarketOverlay | None = None, cfg: dict[str, Any] | None = None) -> GateResult:
    return evaluate_execution_gate(cluster, overlay, cfg)


def apply_execution_gate(
    ranked_candidates: list[dict[str, Any]],
    overlays: dict[str, MarketOverlay],
    max_candidates: int = 15,
    cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    survivors: list[dict[str, Any]] = []
    eliminated: list[dict[str, Any]] = []
    for item in ranked_candidates:
        cluster_payload = item.get("cluster") or {}
        cluster = CandidateCluster(**cluster_payload) if isinstance(cluster_payload, dict) else cluster_payload
        overlay = overlays.get(cluster.primary_ticker)
        result = evaluate_execution_gate(cluster, overlay, cfg)
        decision = ExecutionGateDecision(
            ticker=cluster.primary_ticker,
            passed=result.passed,
            execution_readiness_score=round(overlay.execution_readiness_score if overlay else 0.0, 3),
            blockers=result.reasons,
            warnings=list((overlay.execution_warnings if overlay else []) or []),
        )
        payload = dict(item)
        payload["overlay"] = overlay.to_dict() if overlay else None
        payload["execution_gate"] = decision.to_dict()
        payload["lane_tags"] = classify_candidate_lanes(cluster, overlay)
        payload["hyper_trade"] = score_hyper_trade(cluster, overlay)
        payload["gate_result"] = {
            "passed": result.passed,
            "reasons": result.reasons,
            "score": result.score,
            "hard_blockers": result.hard_blockers or [],
            "speculative_risk_penalties": result.speculative_risk_penalties or [],
        }
        if result.passed:
            survivors.append(payload)
        else:
            eliminated.append(payload)

    survivors.sort(key=lambda item: (item["gate_result"]["score"], item.get("research_priority_score", 0.0)), reverse=True)
    eliminated.sort(key=lambda item: (item["gate_result"]["score"], item.get("research_priority_score", 0.0)), reverse=True)
    return survivors[:max_candidates], eliminated


def shortlist_clusters(
    clusters: list[CandidateCluster],
    overlays: dict[str, MarketOverlay],
    max_candidates: int = 15,
    cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked = rank_clusters_for_research(clusters)
    return apply_execution_gate(ranked, overlays, max_candidates=max_candidates, cfg=cfg)
