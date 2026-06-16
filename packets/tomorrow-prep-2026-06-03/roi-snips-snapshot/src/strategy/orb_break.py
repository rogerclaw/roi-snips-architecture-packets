from __future__ import annotations

from typing import Any

from .second_leg_continuation import evaluate_second_leg_continuation


def evaluate_orb_break(**kwargs: Any) -> dict[str, Any]:
    result = evaluate_second_leg_continuation(**kwargs)
    if result.get("action") == "BUY_NOW" and result.get("mode") == "ORB_BREAK_LONG":
        return result
    if result.get("action") == "BUY_NOW":
        return {**result, "action": "WAIT", "reason": "orb_break_not_confirmed", "failed_predicates": ["orb_break_trigger_ok"]}
    return result

