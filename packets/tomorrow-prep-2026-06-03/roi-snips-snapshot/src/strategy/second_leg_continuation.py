from __future__ import annotations

from typing import Any

from ..research import lifecycle as lc


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _volume_expanding(volumes: list[float], multiplier: float = 1.15) -> bool:
    if len(volumes) < 4:
        return False
    baseline = sum(volumes[-4:-1]) / 3.0
    return baseline > 0 and volumes[-1] >= baseline * multiplier


def evaluate_second_leg_continuation(
    *,
    symbol: str,
    closes: list[float],
    lows: list[float],
    highs: list[float],
    volumes: list[float],
    vwaps: list[float],
    spread_bps: float,
    premarket_high: float | None = None,
    opening_range_high: float | None = None,
    opening_range_low: float | None = None,
    max_spread_bps: float = 80.0,
    max_chase_pct: float = 3.0,
) -> dict[str, Any]:
    if len(closes) < 6 or len(volumes) < 6 or len(vwaps) < 6:
        return {"action": "WAIT", "reason": "needs_more_regular_bars", "failed_predicates": ["enough_regular_bars"], "mode": "SECOND_LEG_CONTINUATION_LONG", "lifecycle_state": lc.SECOND_LEG_RESET}
    last = _f(closes[-1])
    prev = _f(closes[-2])
    vwap = _f(vwaps[-1], last)
    prev_vwap = _f(vwaps[-2], prev)
    base_high = _f(opening_range_high, max(highs[-6:-1] or [last]))
    base_low = _f(opening_range_low, min(lows[-6:] or [last]))
    volume_ok = _volume_expanding([_f(v) for v in volumes])
    spread_ok = spread_bps <= max_spread_bps
    higher_low = min(lows[-3:]) >= base_low * 0.995 if base_low else True
    vwap_reclaim = prev <= prev_vwap and last > vwap
    base_break = last > base_high
    premarket_reclaim = bool(premarket_high and prev <= premarket_high < last)
    trigger_level = max([value for value in [base_high, vwap, premarket_high or 0.0] if value > 0] or [last])
    chase_pct = ((last / max(trigger_level, 0.01)) - 1.0) * 100.0
    chase_ok = chase_pct <= max_chase_pct
    predicates = {
        "spread_ok": spread_ok,
        "volume_expansion_ok": volume_ok,
        "higher_low_ok": higher_low,
        "fresh_trigger_ok": bool(vwap_reclaim or base_break or premarket_reclaim),
        "chase_risk_ok": chase_ok,
    }
    passed = [key for key, value in predicates.items() if value]
    failed = [key for key, value in predicates.items() if not value]
    mode = "SECOND_LEG_CONTINUATION_LONG"
    if vwap_reclaim:
        mode = "VWAP_RECLAIM_LONG"
    elif base_break:
        mode = "ORB_BREAK_LONG"
    elif premarket_reclaim:
        mode = "PREMARKET_HIGH_RECLAIM_LONG"
    if failed:
        if "spread_ok" in failed:
            action = "CANCEL_PRIMARY"
        elif not higher_low:
            action = "SWITCH_TO_BACKUP"
        elif "chase_risk_ok" in failed:
            action = "NO_TRADE_EXTENDED"
        else:
            action = "WAIT"
        return {
            "action": action,
            "reason": "second_leg_predicates_failed",
            "mode": mode,
            "lifecycle_state": lc.SECOND_LEG_RESET if action in {"WAIT", "SWITCH_TO_BACKUP"} else (lc.NO_TRADE_EXTENDED if action == "NO_TRADE_EXTENDED" else lc.EXHAUSTED_OR_DISTRIBUTING),
            "failed_predicates": failed,
            "passed_predicates": passed,
            "actuals": {
                "last": round(last, 4),
                "vwap": round(vwap, 4),
                "base_high": round(base_high, 4),
                "base_low": round(base_low, 4),
                "spread_bps": round(spread_bps, 4),
                "chase_pct": round(chase_pct, 4),
                "last_volume": round(_f(volumes[-1]), 2),
            },
        }
    return {
        "action": "BUY_NOW",
        "reason": "second_leg_continuation_confirmed",
        "mode": mode,
        "trigger": mode.replace("_LONG", ""),
        "lifecycle_state": lc.OPENING_CONTINUATION_ACTIVE,
        "failed_predicates": [],
        "passed_predicates": passed,
        "entry": round(last, 2),
        "stop": round(min(lows[-3:]), 2),
        "actuals": {
            "last": round(last, 4),
            "vwap": round(vwap, 4),
            "base_high": round(base_high, 4),
            "base_low": round(base_low, 4),
            "spread_bps": round(spread_bps, 4),
            "chase_pct": round(chase_pct, 4),
            "last_volume": round(_f(volumes[-1]), 2),
        },
    }
