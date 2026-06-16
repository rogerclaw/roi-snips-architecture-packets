"""Deterministic risk checks for playbook-aligned Opening-Drive v2."""

from __future__ import annotations

from typing import Any


REQUIRED_FIELDS = [
    "ticker",
    "direction",
    "trigger",
    "entry",
    "stop",
    "target_1",
    "shares",
    "notional_usd",
    "max_risk_usd",
    "spread_bps",
    "max_slippage_bps",
]


ALLOWED_TRIGGERS = {
    "OPENING_DRIVE_LONG",
    "OPENING_BURST_HYPER_LONG",
    "OPENING_BURST",
    "ORB_BREAK",
    "PREMARKET_HIGH_RECLAIM",
    "PREMARKET_SURGE",
    "SOCIAL_TAPE_ROCKET",
    "STAGED_OPEN_ORDER",
    "VWAP_RECLAIM",
    "SECOND_LEG_CONTINUATION",
    "SECOND_LEG_CONTINUATION_LONG",
    "ORB_BREAK_LONG",
    "VWAP_RECLAIM_LONG",
    "PREMARKET_HIGH_RECLAIM_LONG",
}
ALLOWED_MODES = set(ALLOWED_TRIGGERS)


def _f(value: Any) -> float:
    return float(value)


def validate_trade_plan(plan: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, str]:
    missing = [k for k in REQUIRED_FIELDS if k not in plan]
    if missing:
        return False, f"missing_fields:{','.join(missing)}"

    if str(plan.get("direction", "")).upper() != "LONG":
        return False, "direction_not_long"

    strategy_family = str(plan.get("strategy_family") or "CatalystContinuationLong")
    if strategy_family != "CatalystContinuationLong":
        return False, "strategy_family_not_allowed"

    trigger = str(plan.get("trigger") or "").upper()
    mode = str(plan.get("mode") or trigger or "VWAP_RECLAIM").upper()
    if mode not in ALLOWED_MODES:
        return False, "mode_not_allowed"

    if trigger not in ALLOWED_TRIGGERS:
        return False, "trigger_not_allowed"

    entry = _f(plan["entry"])
    stop = _f(plan["stop"])
    target_1 = _f(plan["target_1"])
    shares = int(plan["shares"])
    notional = _f(plan["notional_usd"])
    risk = _f(plan["max_risk_usd"])
    spread_bps = _f(plan["spread_bps"])
    slippage_bps = _f(plan["max_slippage_bps"])

    is_opening_drive = mode in {"OPENING_DRIVE_LONG", "OPENING_BURST_HYPER_LONG", "OPENING_BURST", "SOCIAL_TAPE_ROCKET", "STAGED_OPEN_ORDER"} or trigger in {"OPENING_DRIVE_LONG", "OPENING_BURST_HYPER_LONG", "OPENING_BURST", "SOCIAL_TAPE_ROCKET", "STAGED_OPEN_ORDER"}
    max_notional_allowed = float(cfg.get("opening_drive_notional_usd_max", cfg["initial_notional_max_usd"])) if is_opening_drive else float(cfg["initial_notional_max_usd"])
    max_risk_allowed = float(cfg.get("opening_drive_max_trade_risk_usd", cfg["max_trade_risk_usd"])) if is_opening_drive else float(cfg["max_trade_risk_usd"])
    max_spread_allowed = float(cfg.get("opening_drive_max_spread_bps", cfg["max_spread_bps"])) if is_opening_drive else float(cfg["max_spread_bps"])
    max_slippage_allowed = float(cfg.get("opening_drive_max_slippage_bps", cfg.get("max_slippage_bps", slippage_bps))) if is_opening_drive else float(cfg.get("max_slippage_bps", slippage_bps))

    if entry <= 0 or stop <= 0 or target_1 <= 0:
        return False, "non_positive_price"

    if shares <= 0:
        return False, "shares_not_positive"

    if entry <= stop:
        return False, "entry_not_above_stop"

    if target_1 <= entry:
        return False, "target_not_above_entry"

    if float(plan.get("risk_per_share", entry - stop) or 0) <= 0:
        return False, "invalid_initial_stop"

    if notional < float(cfg["initial_notional_min_usd"]):
        return False, "notional_below_min"

    if notional > max_notional_allowed:
        return False, "notional_above_max"

    if risk > max_risk_allowed:
        return False, "trade_risk_exceeded"

    if spread_bps > max_spread_allowed:
        return False, "spread_too_wide"

    if slippage_bps > max_slippage_allowed:
        return False, "slippage_too_high"

    max_open_positions = int(cfg.get("max_open_positions", 1))
    if int(plan.get("open_positions", 0)) >= max_open_positions:
        return False, "max_open_positions_reached"
    if int(plan.get("open_orders", 0)) > 0:
        return False, "open_orders_active"

    order_type = str(plan.get("order_type") or "LIMIT").upper()
    tif = str(plan.get("time_in_force") or "DAY").upper()
    extended_hours = bool(plan.get("extended_hours", False))
    if order_type != "LIMIT":
        return False, "market_order_not_allowed"
    if extended_hours:
        return False, "extended_hours_not_allowed"
    if tif != "DAY":
        return False, "time_in_force_not_allowed"
    if str(plan.get("force_flat_time") or "15:45:00") != "15:45:00":
        return False, "force_flat_time_not_allowed"

    if is_opening_drive:
        first_minute_volume = float(plan.get("first_minute_volume") or 0)
        first_minute_dollar_volume = float(plan.get("first_minute_dollar_volume") or 0)
        close_in_range_pct = float(plan.get("close_in_range_pct") or 0)
        if first_minute_volume < float(cfg.get("opening_drive_min_first_minute_volume", 0)):
            return False, "opening_drive_first_minute_volume_too_low"
        if first_minute_dollar_volume < float(cfg.get("opening_drive_min_first_minute_dollar_volume", 0)):
            return False, "opening_drive_first_minute_dollar_volume_too_low"
        if close_in_range_pct < float(cfg.get("opening_drive_min_close_in_range_pct", 0)):
            return False, "opening_drive_close_quality_too_low"
        reference_price = float(plan.get("opening_drive_reference_price") or 0)
        max_chase_pct = float(cfg.get("opening_drive_max_chase_pct", 0))
        hard_max_entry_price = float(plan.get("hard_max_entry_price") or entry)
        if reference_price > 0 and max_chase_pct > 0:
            allowed_price = reference_price * (1 + (max_chase_pct / 100.0))
            if hard_max_entry_price > allowed_price + 1e-9:
                return False, "opening_drive_chase_limit_exceeded"

    expected_upside = float(plan.get("target_1", target_1)) - entry
    estimated_cost = entry * ((spread_bps + slippage_bps) / 10000.0)
    if expected_upside < ((entry - stop) * 1.0) + estimated_cost:
        return False, "upside_after_costs_too_small"

    return True, "ok"
