from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .readiness_types import MorningReadinessResult


REQUIRED_REBUILD_ARTIFACTS = [
    "morning_control_plane",
    "broad_discovery",
    "research_war_room",
    "candidate_tournament",
    "catalyst_strategy_router",
    "opening_bell_engine",
    "continuation_engine",
    "event_timed_engine",
    "execution_plan",
    "post_miss_learning",
    "no_order_attestation",
]


@dataclass
class ArtifactGateResult:
    ready: bool
    missing_artifacts: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    no_order_attestation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_artifact_gate(artifacts: dict[str, Any]) -> ArtifactGateResult:
    missing = [name for name in REQUIRED_REBUILD_ARTIFACTS if not artifacts.get(name)]
    blockers: list[str] = []
    warnings: list[str] = []

    attestation = artifacts.get("no_order_attestation") or {}
    no_order = bool(attestation.get("brokerless") and attestation.get("orders_submitted") is False)
    if not no_order:
        blockers.append("missing_brokerless_no_order_attestation")

    control = artifacts.get("morning_control_plane") or {}
    if control and not control.get("brokerless_shadow_only"):
        blockers.append("morning_control_plane_not_brokerless")

    discovery = artifacts.get("broad_discovery") or {}
    if discovery and discovery.get("candidate_count", 0) < 1:
        blockers.append("broad_discovery_empty")

    tournament = artifacts.get("candidate_tournament") or {}
    if not tournament.get("best_pick"):
        blockers.append("missing_best_pick")
    if tournament.get("stale_winner_blocked") is False:
        blockers.append("stale_prior_winner_not_blocked")
    if tournament.get("mega_cap_fallback_blocked") is False:
        blockers.append("mega_cap_fallback_not_blocked")

    route = artifacts.get("catalyst_strategy_router") or {}
    if route and not route.get("allowed_modes"):
        blockers.append("strategy_router_returned_no_allowed_modes")
    if route and route.get("broker_action") != "NONE":
        blockers.append("strategy_router_attempted_broker_action")

    plan = artifacts.get("execution_plan") or {}
    if plan and plan.get("broker_action") != "NONE":
        blockers.append("execution_plan_attempted_broker_action")

    return ArtifactGateResult(
        ready=not missing and not blockers,
        missing_artifacts=missing,
        blockers=blockers,
        warnings=warnings,
        no_order_attestation=no_order,
    )


def evaluate_morning_readiness(
    artifacts: dict[str, Any],
    *,
    stream_required: bool = True,
    requested_proof_scope: str = "MARKET_OPEN_READINESS",
) -> MorningReadinessResult:
    """Evaluate runbook-level readiness from persisted morning proof artifacts.

    This is stricter than the clean-rebuild foundation gate: it validates the
    scheduler canary, same-day packet, source lane status, stream symbol proof,
    no-order attestation, and brokerless constraints before any ready state.
    """

    failure_reasons: list[str] = []
    warnings: list[str] = []

    canary = artifacts.get("canary") or {}
    same_day_packet = artifacts.get("same_day_packet") or {}
    source_lane_status = artifacts.get("source_lane_status") or {}
    stream = artifacts.get("stream_summary") or {}
    tournament = artifacts.get("candidate_tournament") or {}
    broad_discovery = artifacts.get("broad_discovery") or {}

    canary_passed = canary.get("status") == "PASS"
    if not canary_passed:
        failure_reasons.append("canary_missing_or_failed")

    same_day_packet_ready = bool(same_day_packet)
    if not same_day_packet_ready:
        failure_reasons.append("same_day_packet_missing")

    if not source_lane_status:
        failure_reasons.append("source_lane_status_missing")

    source_breadth_status = str(source_lane_status.get("source_breadth_status") or source_lane_status.get("status") or "UNKNOWN")
    raw_candidate_count = int(broad_discovery.get("raw_candidate_count") or broad_discovery.get("candidate_count") or 0)
    discovery_status = str(broad_discovery.get("status") or "").upper()
    if raw_candidate_count < 10 and discovery_status not in {"DEGRADED", "NO_TRADE_RESEARCH_INCOMPLETE", "FAILED", "SEVERELY_DEGRADED"}:
        failure_reasons.append("raw_candidate_count_too_low_without_degraded_status")

    same_style_backup_ok = tournament.get("same_style_backup_pool_ok")
    backup_pool_status = str(tournament.get("backup_pool_status") or "UNKNOWN")
    if same_style_backup_ok is False and backup_pool_status.upper() not in {"DEGRADED", "FAILED", "NO_TRADE_RESEARCH_INCOMPLETE"}:
        failure_reasons.append("same_style_backup_failure_without_degraded_status")

    broker_account_inspected = bool(artifacts.get("broker_account_inspected") or same_day_packet.get("broker_account_inspected"))
    broker_orders_inspected = bool(artifacts.get("broker_orders_inspected") or same_day_packet.get("broker_orders_inspected"))
    broker_positions_inspected = bool(artifacts.get("broker_positions_inspected") or same_day_packet.get("broker_positions_inspected"))
    if broker_account_inspected or broker_orders_inspected or broker_positions_inspected:
        failure_reasons.append("broker_inspected_in_brokerless_mode")

    orders_submitted = bool(artifacts.get("orders_submitted") or same_day_packet.get("orders_submitted"))
    orders_previewed = bool(artifacts.get("orders_previewed") or same_day_packet.get("orders_previewed"))
    orders_canceled = bool(artifacts.get("orders_canceled") or same_day_packet.get("orders_canceled"))
    if orders_submitted or orders_previewed or orders_canceled:
        failure_reasons.append("order_action_in_no_order_mode")

    symbols = artifacts.get("symbols") or same_day_packet.get("symbols") or same_day_packet.get("discovered_symbols") or []
    if not symbols:
        failure_reasons.append("stream_symbols_missing")

    stream_captured = bool(stream.get("stream_captured") or stream.get("stream_capture_completed"))
    stream_skipped = stream.get("reason") == "stream_skipped" or stream.get("stream_skipped") is True
    if stream_required and (not stream or stream_skipped or not stream_captured):
        failure_reasons.append("required_stream_summary_missing_or_skipped")

    opening_burst_window_covered = bool(stream.get("opening_burst_window_covered") or stream.get("opening_window_covered"))
    continuation_window_covered = bool(stream.get("continuation_window_covered"))
    proof_scope = requested_proof_scope
    if requested_proof_scope == "MARKET_OPEN_READINESS" and stream.get("proof_scope") == "CONNECTIVITY_ONLY":
        failure_reasons.append("connectivity_only_claimed_as_market_open_readiness")
        proof_scope = "CONNECTIVITY_ONLY"

    if requested_proof_scope == "MARKET_OPEN_READINESS" and stream_required and not opening_burst_window_covered:
        failure_reasons.append("opening_burst_window_not_covered")

    if not continuation_window_covered:
        warnings.append("continuation_window_not_proven")

    final_status = "READY" if not failure_reasons else "FAIL"
    if "connectivity_only_claimed_as_market_open_readiness" in failure_reasons:
        final_status = "CONNECTIVITY_ONLY"
    if any(reason in failure_reasons for reason in ["canary_missing_or_failed", "same_day_packet_missing", "source_lane_status_missing"]):
        final_status = "INTERNAL_FAILURE"

    ready_for_no_order = final_status == "READY"
    human_summary = "Brokerless no-order morning proof is ready." if ready_for_no_order else "Morning readiness blocked: " + ", ".join(failure_reasons)

    return MorningReadinessResult(
        final_status=final_status,
        proof_scope=proof_scope,
        ready_for_live=False,
        ready_for_paper=False,
        ready_for_no_order=ready_for_no_order,
        canary_passed=canary_passed,
        research_war_room_passed=bool(artifacts.get("research_war_room")),
        source_breadth_status=source_breadth_status,
        backup_pool_status=backup_pool_status,
        same_day_packet_ready=same_day_packet_ready,
        stream_captured=stream_captured,
        opening_burst_window_covered=opening_burst_window_covered,
        continuation_window_covered=continuation_window_covered,
        orders_submitted=orders_submitted,
        broker_account_inspected=broker_account_inspected,
        broker_orders_inspected=broker_orders_inspected,
        broker_positions_inspected=broker_positions_inspected,
        failure_reasons=failure_reasons,
        warnings=warnings,
        human_summary=human_summary,
    )
