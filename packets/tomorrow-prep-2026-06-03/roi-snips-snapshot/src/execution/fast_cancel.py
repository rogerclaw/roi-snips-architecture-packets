"""Fast cancel decisions for opening-burst orders."""

from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        parsed = float(value)
    except Exception:
        return default
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return default
    return parsed


def _malformed_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        parsed = float(value)
    except Exception:
        return True
    return parsed != parsed or parsed in {float("inf"), float("-inf")}


def should_fast_cancel(order_state: dict[str, Any], tape: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, str]:
    if order_state.get("status") in {"filled", "cancelled", "rejected"}:
        return False, "terminal_order_state"
    if tape.get("tape_state") in {"HALT_OR_NO_QUOTE", "SPREAD_EXPLODED", "STALE_DATA", "DRIVE_FAILED", "GAP_AND_CRAP"}:
        return True, str(tape.get("tape_state")).lower()
    if tape.get("bid_collapse_flag"):
        return True, "bid_collapse"
    numeric_values = [
        order_state.get("entry_cap"),
        order_state.get("hard_max_entry_price"),
        order_state.get("elapsed_seconds"),
        order_state.get("cancel_after_seconds"),
        order_state.get("replace_count"),
        tape.get("latest_price"),
        tape.get("opening_drive_score"),
    ]
    if any(_malformed_number(value) for value in numeric_values):
        return True, "malformed_numeric_input"
    entry_cap = _safe_float(order_state.get("entry_cap") or order_state.get("hard_max_entry_price"), 0.0)
    latest = _safe_float(tape.get("latest_price"), 0.0)
    if entry_cap > 0 and latest > entry_cap:
        return True, "price_above_entry_cap_before_fill"
    opening_drive_score = _safe_float(tape.get("opening_drive_score"), 0.0)
    elapsed_seconds = _safe_float(order_state.get("elapsed_seconds"), 0.0)
    cancel_after_seconds = max(_safe_float(order_state.get("cancel_after_seconds"), 3.0), 0.0)
    if opening_drive_score < 6.0 and elapsed_seconds >= cancel_after_seconds:
        return True, "unfilled_and_tape_weak"
    if _safe_float(order_state.get("replace_count"), 0.0) > 1:
        return True, "replace_limit_exceeded"
    return False, "hold_order"
