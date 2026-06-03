from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_gap_and_go_confirmation(candidate: dict[str, Any], tape: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    gap_pct = _f(candidate.get("gap_pct") or tape.get("gap_pct"))
    spread_bps = _f(tape.get("spread_bps"), 9999.0)
    drive = _f(tape.get("opening_drive_score"))
    volume = max(_f(tape.get("volume_burst_ratio")), _f(tape.get("absolute_dollar_volume_score")))

    if tape.get("tape_state") in {"GAP_AND_CRAP", "BID_COLLAPSE", "SPREAD_EXPLODED", "HALT_OR_NO_QUOTE"}:
        blockers.append(str(tape.get("tape_state")).lower())
    if not tape.get("price_above_open"):
        blockers.append("price_not_above_open")
    if gap_pct < 5:
        blockers.append("gap_below_runbook_threshold")
    if drive < 7.5:
        blockers.append("opening_drive_not_confirmed")
    if volume < 7:
        blockers.append("volume_not_confirmed")
    if spread_bps > 80:
        blockers.append("spread_too_wide")

    if blockers:
        return {
            "action": "NO_TRADE" if any(b in blockers for b in ["gap_and_crap", "bid_collapse", "spread_exploded"]) else "WAIT",
            "mode": "GAP_AND_GO_CONFIRMATION",
            "broker_action": "NONE",
            "order_type": "AGGRESSIVE_LIMIT_ONLY",
            "blockers": sorted(set(blockers)),
        }
    return {
        "action": "BUY_NOW",
        "mode": "GAP_AND_GO_CONFIRMATION",
        "broker_action": "NONE",
        "order_type": "AGGRESSIVE_LIMIT_ONLY",
        "limit_price": round(_f(tape.get("ask") or candidate.get("entry")), 2),
        "passed_predicates": ["gap_ok", "price_above_open", "drive_ok", "volume_ok", "spread_ok"],
    }
