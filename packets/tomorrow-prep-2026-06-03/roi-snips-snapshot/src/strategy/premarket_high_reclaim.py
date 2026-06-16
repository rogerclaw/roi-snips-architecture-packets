from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_premarket_high_reclaim(candidate: dict[str, Any], tape: dict[str, Any]) -> dict[str, Any]:
    price = _f(tape.get("last") or tape.get("price"))
    premarket_high = _f(candidate.get("premarket_high") or tape.get("premarket_high"))
    spread_bps = _f(tape.get("spread_bps"), 9999.0)
    volume = max(_f(tape.get("volume_burst_ratio")), _f(tape.get("relative_volume_score")))
    reclaim_confirmed = bool(tape.get("premarket_high_reclaim_confirmed") or (premarket_high > 0 and price > premarket_high))

    blockers: list[str] = []
    if not reclaim_confirmed:
        blockers.append("premarket_high_not_reclaimed")
    if volume < 6.5:
        blockers.append("volume_not_confirmed")
    if spread_bps > 90:
        blockers.append("spread_too_wide")

    if blockers:
        return {"action": "WAIT", "mode": "PREMARKET_HIGH_RECLAIM", "broker_action": "NONE", "blockers": blockers}
    return {
        "action": "BUY_NOW",
        "mode": "PREMARKET_HIGH_RECLAIM",
        "broker_action": "NONE",
        "order_type": "AGGRESSIVE_LIMIT_ONLY",
        "trigger_level": round(premarket_high, 2),
        "entry": round(price, 2),
    }
