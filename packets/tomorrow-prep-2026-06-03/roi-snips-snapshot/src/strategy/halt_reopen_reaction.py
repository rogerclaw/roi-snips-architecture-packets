from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_halt_reopen_reaction(candidate: dict[str, Any], tape: dict[str, Any]) -> dict[str, Any]:
    if tape.get("halt_active") or tape.get("tape_state") == "HALT_OR_NO_QUOTE":
        return {
            "action": "WAIT",
            "mode": "HALT_REOPEN_REACTION",
            "broker_action": "NONE",
            "blockers": ["halt_active_or_no_quote"],
        }

    spread_bps = _f(tape.get("spread_bps"), 9999.0)
    drive = _f(tape.get("reopen_drive_score") or tape.get("opening_drive_score"))
    volume = max(_f(tape.get("reopen_volume_score")), _f(tape.get("volume_burst_ratio")))
    blockers: list[str] = []
    if not tape.get("halt_reopen"):
        blockers.append("halt_reopen_not_detected")
    if drive < 7.5:
        blockers.append("reopen_drive_not_confirmed")
    if volume < 7:
        blockers.append("reopen_volume_not_confirmed")
    if spread_bps > 120:
        blockers.append("spread_too_wide_after_halt")

    if blockers:
        return {"action": "WAIT", "mode": "HALT_REOPEN_REACTION", "broker_action": "NONE", "blockers": blockers}
    return {
        "action": "BUY_NOW",
        "mode": "HALT_REOPEN_REACTION",
        "broker_action": "NONE",
        "order_type": "AGGRESSIVE_LIMIT_ONLY",
        "entry": round(_f(tape.get("last") or tape.get("ask")), 2),
    }
