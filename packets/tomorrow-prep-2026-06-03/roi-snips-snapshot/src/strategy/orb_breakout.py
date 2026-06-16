from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_orb_breakout(candidate: dict[str, Any], tape: dict[str, Any], *, minutes: int = 1) -> dict[str, Any]:
    mode = "ORB_BREAK_5MIN" if minutes >= 5 else "ORB_BREAK_1MIN"
    price = _f(tape.get("last") or tape.get("price"))
    range_high = _f(tape.get("opening_range_high") or tape.get("orb_high"))
    range_low = _f(tape.get("opening_range_low") or tape.get("orb_low"))
    volume = max(_f(tape.get("volume_burst_ratio")), _f(tape.get("continuation_volume_expansion_score")))
    spread_bps = _f(tape.get("spread_bps"), 9999.0)

    blockers: list[str] = []
    if not (range_high > 0 and price > range_high):
        blockers.append("opening_range_not_broken")
    if range_low > 0 and price < range_low:
        blockers.append("range_failed")
    if volume < 6.5:
        blockers.append("volume_not_confirmed")
    if spread_bps > 90:
        blockers.append("spread_too_wide")

    if blockers:
        return {"action": "WAIT", "mode": mode, "broker_action": "NONE", "blockers": blockers}
    return {
        "action": "BUY_NOW",
        "mode": mode,
        "broker_action": "NONE",
        "order_type": "AGGRESSIVE_LIMIT_ONLY",
        "entry": round(price, 2),
        "trigger_level": round(range_high, 2),
    }
