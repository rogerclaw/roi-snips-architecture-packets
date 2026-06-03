"""Dedicated opening-bell burst strategy."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _positive_finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _cfg(root: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = root
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _window_name(now: datetime, cfg: dict[str, Any]) -> str:
    local = now.astimezone(ZoneInfo("America/New_York"))
    seconds = (local.hour * 3600) + (local.minute * 60) + local.second
    ranges = {
        "observe": (9 * 3600 + 30 * 60, 9 * 3600 + 30 * 60 + 5),
        "first_10s": (9 * 3600 + 30 * 60 + 5, 9 * 3600 + 30 * 60 + 15),
        "first_30s": (9 * 3600 + 30 * 60 + 15, 9 * 3600 + 30 * 60 + 30),
        "first_60s": (9 * 3600 + 30 * 60 + 30, 9 * 3600 + 31 * 60),
        "continuation": (9 * 3600 + 31 * 60, 9 * 3600 + 31 * 60 + 30),
        "rescue_or_reclaim": (9 * 3600 + 31 * 60 + 30, 9 * 3600 + 35 * 60),
    }
    for name, (start, end) in ranges.items():
        if start <= seconds < end:
            return name
    return "fallback_or_closed"


def _threshold_bucket(window: str) -> str:
    if window in {"first_10s", "first_30s", "first_60s"}:
        return window
    if window == "continuation":
        return "first_60s"
    if window == "rescue_or_reclaim":
        return "first_60s"
    return "first_30s"


def _predicate_report(predicates: dict[str, bool], actuals: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed_predicates": [key for key, value in predicates.items() if value],
        "failed_predicates": [key for key, value in predicates.items() if not value],
        "actuals": actuals,
        "thresholds": thresholds,
    }


def size_for_spread(candidate: dict[str, Any], tape: dict[str, Any], cfg: dict[str, Any]) -> float:
    sizing = _cfg(cfg, "opening_bell", "sizing", default={}) or {}
    spread = _f(tape.get("spread_bps"), 9999.0)
    lane_tags = set(candidate.get("lane_tags") or [])
    verified = "VERIFIED_CATALYST_RUNNER" in lane_tags
    base = float(sizing.get("verified_default_usd" if verified else "social_tape_default_usd", 300 if verified else 100))
    if _f(candidate.get("hyper_trade_score"), 0.0) >= 8.5 and verified:
        base = float(sizing.get("verified_strong_usd", 500))
    if _f(candidate.get("hyper_trade_score"), 0.0) >= 9.0:
        base = min(float(sizing.get("a_plus_max_usd", 1000)), base * 2)
    if spread > 100:
        base = min(base, float(sizing.get("social_tape_max_usd", 300)))
    if spread > 200:
        base = min(base, 100.0)
    return round(max(0.0, base), 2)


def evaluate_opening_burst_signal(
    candidate: dict[str, Any],
    tape: dict[str, Any],
    cfg: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    window = _window_name(now, cfg)
    if window == "observe":
        return {"action": "WAIT", "reason": "first_print_observe_window", "window": window, "failed_predicates": ["observe_first_print_until_09_30_05"]}
    if window == "fallback_or_closed":
        return {"action": "WAIT", "reason": "opening_burst_window_closed_handoff_to_continuation", "window": window, "failed_predicates": ["opening_burst_window_closed", "continuation_handoff_required"]}

    hard_blockers: list[str] = []
    bid = _positive_finite(tape.get("bid"))
    ask_value = _positive_finite(tape.get("ask"))
    if bid is None or ask_value is None:
        hard_blockers.append("missing_bid_ask")
    elif ask_value <= bid:
        hard_blockers.append("invalid_bid_ask")
    if _f(tape.get("quote_age_ms"), 999999.0) > float(_cfg(cfg, "opening_bell", "data", "max_quote_age_ms", default=1000)):
        hard_blockers.append("stale_quote")
    if tape.get("tape_state") in {"HALT_OR_NO_QUOTE", "SPREAD_EXPLODED", "STALE_DATA", "DRIVE_FAILED", "GAP_AND_CRAP"}:
        hard_blockers.append(str(tape.get("tape_state")).lower())
    if tape.get("bid_collapse_flag"):
        hard_blockers.append("bid_collapse")
    if hard_blockers:
        return {"action": "NO_TRADE", "reason": "hard_block", "hard_blockers": sorted(set(hard_blockers)), "failed_predicates": sorted(set(hard_blockers)), "window": window}

    thresholds = _cfg(cfg, "opening_bell", "thresholds", _threshold_bucket(window), default={}) or {}
    min_hyper = float(thresholds.get("min_hyper_trade_score", 7.0))
    min_drive = float(thresholds.get("min_opening_drive_score", 7.2))
    min_volume = float(thresholds.get("min_volume_burst_score", 6.5))
    max_rug = float(thresholds.get("max_rug_pull_score", 5.0))
    max_wick = float(thresholds.get("max_upper_wick_fade_score", 5.0))
    max_chase = float(thresholds.get("max_chase_risk_score", 6.0))

    hyper = max(
        _f(candidate.get("hyper_trade_score"), 0.0),
        _f(candidate.get("opening_strategy_score"), 0.0),
        _f(candidate.get("infq_archetype_score"), 0.0),
    )
    drive = _f(tape.get("opening_drive_score"), 0.0)
    volume_score = min(
        max(
            _f(tape.get("volume_burst_ratio"), 0.0),
            _f(tape.get("absolute_dollar_volume_score"), 0.0),
            _f(tape.get("continuation_volume_expansion_score"), 0.0),
            _f(tape.get("volume_quality_after_reset_score"), 0.0),
        ),
        10.0,
    )
    predicates = {
        "hyper_trade_score_ok": hyper >= min_hyper,
        "opening_drive_score_ok": drive >= min_drive,
        "volume_burst_ok": volume_score >= min_volume,
        "rug_pull_risk_ok": _f(tape.get("rug_pull_score"), 0.0) <= max_rug,
        "upper_wick_risk_ok": _f(tape.get("upper_wick_fade_score"), 0.0) <= max_wick,
        "chase_risk_ok": _f(tape.get("chase_risk_score"), 0.0) <= max_chase,
        "open_break_reclaim_or_micro_vwap_hold": bool(
            tape.get("price_above_open")
            or tape.get("premarket_high_break_confirmed")
            or tape.get("premarket_high_reclaim_confirmed")
            or tape.get("micro_vwap_hold")
        ),
    }
    actuals = {
        "hyper_trade_score": hyper,
        "raw_hyper_trade_score": _f(candidate.get("hyper_trade_score"), 0.0),
        "opening_strategy_score": _f(candidate.get("opening_strategy_score"), 0.0),
        "infq_archetype_score": _f(candidate.get("infq_archetype_score"), 0.0),
        "opening_drive_score": drive,
        "volume_burst_score": volume_score,
        "absolute_dollar_volume_score": _f(tape.get("absolute_dollar_volume_score"), 0.0),
        "opening_vs_premarket_rate_score": _f(tape.get("opening_vs_premarket_rate_score"), 0.0),
        "acceleration_vs_previous_window_score": _f(tape.get("acceleration_vs_previous_window_score"), 0.0),
        "continuation_volume_expansion_score": _f(tape.get("continuation_volume_expansion_score"), 0.0),
        "volume_quality_after_reset_score": _f(tape.get("volume_quality_after_reset_score"), 0.0),
        "rug_pull_score": _f(tape.get("rug_pull_score"), 0.0),
        "upper_wick_fade_score": _f(tape.get("upper_wick_fade_score"), 0.0),
        "chase_risk_score": _f(tape.get("chase_risk_score"), 0.0),
        "tape_state": tape.get("tape_state"),
    }
    thresholds_payload = {
        "min_hyper_trade_score": min_hyper,
        "min_opening_drive_score": min_drive,
        "min_volume_burst_score": min_volume,
        "max_rug_pull_score": max_rug,
        "max_upper_wick_fade_score": max_wick,
        "max_chase_risk_score": max_chase,
    }
    predicate_report = _predicate_report(predicates, actuals, thresholds_payload)
    if predicate_report["failed_predicates"]:
        action = "WAIT" if window in {"first_10s", "first_30s", "first_60s"} and not any(key.endswith("_risk_ok") for key in predicate_report["failed_predicates"]) else "NO_TRADE"
        return {"action": action, "reason": "setup_not_confirmed", "window": window, **predicate_report}

    ask = ask_value or 0.0
    entry_cap = _positive_finite(candidate.get("entry_cap") or candidate.get("hard_max_entry_price") or candidate.get("entry")) or 0.0
    slip_bps = float(_cfg(cfg, "opening_bell", "order", "slippage_cap_bps", default=20))
    slip_cents = float(_cfg(cfg, "opening_bell", "order", "slippage_cap_cents", default=0.03))
    dynamic_limit = ask + max(slip_cents, ask * slip_bps / 10000.0)
    final_limit = round(min(dynamic_limit, entry_cap), 2)
    if final_limit <= 0 or final_limit < ask:
        return {"action": "NO_TRADE", "reason": "ask_above_entry_cap", "window": window, "ask": ask, "entry_cap": entry_cap, "failed_predicates": ["ask_at_or_below_entry_cap"]}

    return {
        "action": "BUY_NOW",
        "strategy": "OPENING_BURST_HYPER_LONG",
        "trigger": "OPENING_BURST_HYPER_LONG",
        "mode": "OPENING_BURST_HYPER_LONG",
        "window": window,
        "symbol": candidate.get("ticker") or candidate.get("symbol"),
        "limit_price": final_limit,
        "entry": final_limit,
        "entry_cap": entry_cap,
        "notional_usd": size_for_spread(candidate, tape, cfg),
        "opening_drive_score": round(drive, 3),
        "open_execution_confidence": round(min(_f(tape.get("open_execution_confidence"), drive), drive), 3),
        "hard_blockers": [],
        **predicate_report,
    }
