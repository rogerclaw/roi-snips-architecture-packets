from __future__ import annotations

from typing import Any


def route_momentum_strategy(candidate: dict[str, Any], tape: dict[str, Any] | None = None) -> dict[str, Any]:
    tape = tape or {}
    gap_pct = float(tape.get("gap_pct") or candidate.get("gap_pct") or 0.0)
    minutes_from_open = float(tape.get("minutes_from_open") or 0.0)
    above_vwap = bool(tape.get("above_vwap"))
    opening_range_break = bool(tape.get("opening_range_break"))
    event_minutes = tape.get("event_minutes")

    allowed: list[str] = []
    if 0 <= minutes_from_open <= 5 and gap_pct >= 5:
        allowed.append("OPENING_BURST_HYPER_LONG")
    if 5 <= minutes_from_open <= 90 and above_vwap:
        allowed.append("VWAP_RECLAIM_LONG")
    if 5 <= minutes_from_open <= 90 and opening_range_break:
        allowed.append("ORB_BREAK_LONG")
    if minutes_from_open >= 5:
        allowed.append("SECOND_LEG_CONTINUATION_LONG")
    if event_minutes is not None and 0 <= float(event_minutes) <= 30:
        allowed.append("EVENT_TIMED_MOMENTUM_LONG")

    allowed = sorted(set(allowed))
    return {
        "ticker": candidate.get("ticker"),
        "allowed_modes": allowed,
        "primary_mode": allowed[0] if allowed else None,
        "broker_action": "NONE",
        "requires_live_tape_confirmation": True,
        "engines": {
            "opening_bell": "OPENING_BURST_HYPER_LONG" in allowed,
            "vwap": "VWAP_RECLAIM_LONG" in allowed,
            "orb": "ORB_BREAK_LONG" in allowed,
            "second_leg": "SECOND_LEG_CONTINUATION_LONG" in allowed,
            "event_timed": "EVENT_TIMED_MOMENTUM_LONG" in allowed,
        },
        "deterministic_guards": [
            "long_only",
            "one_position_max",
            "fresh_catalyst_required",
            "live_tape_confirmation_required",
            "brokerless_shadow_output_only",
        ],
    }
