from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..ops.artifact_gate import evaluate_artifact_gate
from ..research.war_room import build_research_war_room, run_candidate_tournament
from ..strategy.momentum_router import route_momentum_strategy


def build_no_order_attestation() -> dict[str, Any]:
    return {
        "brokerless": True,
        "orders_submitted": False,
        "orders_previewed": False,
        "orders_canceled": False,
        "broker_account_inspected": False,
    }


def _engine_artifact(name: str, enabled: bool, mode: str) -> dict[str, Any]:
    return {
        "engine": name,
        "mode": mode,
        "enabled_by_router": enabled,
        "broker_action": "NONE",
        "output": "shadow_signal_only",
    }


def run_clean_rebuild_shadow(candidates: list[dict[str, Any]], tape: dict[str, Any] | None = None) -> dict[str, Any]:
    tournament = run_candidate_tournament(candidates)
    best_row = next((row["candidate"] for row in tournament["ranked"] if row["candidate"]["ticker"] == tournament["best_pick"]), None)
    route = route_momentum_strategy(best_row or {}, tape or {}) if best_row else {"allowed_modes": [], "primary_mode": None, "broker_action": "NONE"}
    engines = route.get("engines") or {}
    artifacts = {
        "morning_control_plane": {
            "status": "shadow_ready",
            "brokerless_shadow_only": True,
            "opens_research_before_execution": True,
            "blocks_stale_winner_recycling": True,
            "blocks_boring_mega_cap_fallback": True,
        },
        "broad_discovery": {
            "candidate_count": len(candidates),
            "status": "deterministic_shadow",
            "minimum_lanes": ["official", "newswire", "premarket_gap", "social_velocity", "theme_sympathy"],
        },
        "research_war_room": build_research_war_room(candidates),
        "candidate_tournament": tournament,
        "catalyst_strategy_router": route,
        "opening_bell_engine": _engine_artifact("opening_bell", bool(engines.get("opening_bell")), "OPENING_BURST_HYPER_LONG"),
        "continuation_engine": {
            "broker_action": "NONE",
            "output": "shadow_signal_only",
            "vwap_reclaim": bool(engines.get("vwap")),
            "orb_break": bool(engines.get("orb")),
            "second_leg": bool(engines.get("second_leg")),
        },
        "event_timed_engine": _engine_artifact("event_timed", bool(engines.get("event_timed")), "EVENT_TIMED_MOMENTUM_LONG"),
        "execution_plan": {
            "mode": route.get("primary_mode"),
            "broker_action": "NONE",
            "requires_operator_or_guarded_runtime": True,
            "entry_surface": "shadow_only_no_order_preview",
            "risk_shape": "long_only_single_position_until_live_guards_authorized",
        },
        "post_miss_learning": {
            "captures_missed_runner_reason": True,
            "records_stale_winner_failures": True,
            "records_false_readiness_blockers": True,
            "broker_action": "NONE",
        },
        "no_order_attestation": build_no_order_attestation(),
    }
    gate = evaluate_artifact_gate(artifacts)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
        "artifact_gate": gate.to_dict(),
        "ready": gate.ready,
    }
