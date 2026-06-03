from __future__ import annotations

from typing import Any

from .second_leg_continuation import evaluate_second_leg_continuation


def evaluate_vwap_reclaim(**kwargs: Any) -> dict[str, Any]:
    result = evaluate_second_leg_continuation(**kwargs)
    if result.get("action") == "BUY_NOW" and result.get("mode") == "VWAP_RECLAIM_LONG":
        return result
    if result.get("action") == "BUY_NOW":
        return {**result, "action": "WAIT", "reason": "vwap_reclaim_not_confirmed", "failed_predicates": ["vwap_reclaim_trigger_ok"]}
    return result

