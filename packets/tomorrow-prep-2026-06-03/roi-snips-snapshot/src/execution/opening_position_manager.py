"""Immediate post-fill opening position manager."""

from __future__ import annotations

from typing import Any


def opening_position_action(position: dict[str, Any], tape: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    qty = float(position.get("qty") or position.get("quantity") or 0.0)
    if qty <= 0:
        return {"action": "NO_POSITION", "reason": "no_positive_quantity"}
    entry = float(position.get("entry_price") or position.get("avg_entry_price") or 0.0)
    thesis_break = float(position.get("thesis_break") or position.get("stop") or 0.0)
    latest = float(tape.get("latest_price") or tape.get("bid") or 0.0)
    elapsed = float(position.get("elapsed_seconds") or 0.0)
    if tape.get("tape_state") in {"HALT_OR_NO_QUOTE", "STALE_DATA"}:
        return {"action": "EXIT", "reason": str(tape.get("tape_state")).lower(), "urgency": "high"}
    if latest and thesis_break and latest <= thesis_break:
        return {"action": "EXIT", "reason": "thesis_break", "urgency": "high"}
    if tape.get("bid_collapse_flag"):
        return {"action": "EXIT", "reason": "bid_collapse", "urgency": "high"}
    if tape.get("tape_state") in {"DRIVE_FAILED", "GAP_AND_CRAP"}:
        return {"action": "EXIT", "reason": str(tape.get("tape_state")).lower(), "urgency": "high"}
    if elapsed >= float((cfg.get("opening_bell") or {}).get("exits", {}).get("time_stop_seconds_soft", 120)):
        if latest <= entry and float(tape.get("opening_drive_score") or 0.0) < 7.0:
            return {"action": "EXIT", "reason": "time_stop_no_continuation", "urgency": "medium"}
    target_1 = float(position.get("target_1") or 0.0)
    if target_1 and latest >= target_1:
        return {"action": "TIGHTEN_OR_TAKE_PROFIT", "reason": "target_1_hit", "urgency": "medium"}
    return {"action": "HOLD", "reason": "position_confirming"}

