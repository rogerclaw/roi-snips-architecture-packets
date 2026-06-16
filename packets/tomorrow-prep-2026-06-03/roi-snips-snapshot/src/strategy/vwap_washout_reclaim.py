from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_vwap_washout_reclaim(candidate: dict[str, Any], tape: dict[str, Any]) -> dict[str, Any]:
    price = _f(tape.get("last") or tape.get("price"))
    vwap = _f(tape.get("vwap"))
    washed_out = bool(tape.get("vwap_washout_seen") or tape.get("washed_below_vwap"))
    reclaimed = bool(tape.get("vwap_washout_reclaim_confirmed") or (washed_out and vwap > 0 and price > vwap))
    higher_low = bool(tape.get("higher_low_confirmed"))
    volume = max(_f(tape.get("volume_burst_ratio")), _f(tape.get("continuation_volume_expansion_score")))
    spread_bps = _f(tape.get("spread_bps"), 9999.0)

    blockers: list[str] = []
    if not reclaimed:
        blockers.append("vwap_washout_reclaim_not_confirmed")
    if not higher_low:
        blockers.append("higher_low_not_confirmed")
    if volume < 6.5:
        blockers.append("volume_not_confirmed")
    if spread_bps > 90:
        blockers.append("spread_too_wide")

    if blockers:
        return {"action": "WAIT", "mode": "VWAP_WASHOUT_RECLAIM", "broker_action": "NONE", "blockers": blockers}
    return {
        "action": "BUY_NOW",
        "mode": "VWAP_WASHOUT_RECLAIM",
        "broker_action": "NONE",
        "order_type": "AGGRESSIVE_LIMIT_ONLY",
        "entry": round(price, 2),
        "stop_reference": "higher_low_or_vwap_loss",
    }
