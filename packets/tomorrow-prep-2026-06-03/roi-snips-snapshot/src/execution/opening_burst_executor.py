"""Executor adapter for OPENING_BURST_HYPER_LONG signals."""

from __future__ import annotations

from typing import Any

from ..common.runtime_state import active_guards
from ..common.config import risk_config_for_validation
from ..risk.rules import validate_trade_plan
from .order_router import OrderRouter


def build_opening_burst_plan(signal: dict[str, Any], candidate: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    entry = round(float(signal["limit_price"]), 2)
    stop = round(float(candidate.get("thesis_break") or candidate.get("stop") or entry * 0.97), 2)
    notional = round(float(signal.get("notional_usd") or candidate.get("notional_usd") or 100.0), 2)
    shares = max(1, int(notional // entry))
    target_1 = round(float(candidate.get("target_1") or entry + ((entry - stop) * 1.5)), 2)
    return {
        "plan_id": signal.get("plan_id") or f"opening_burst_{signal.get('symbol')}",
        "ticker": signal.get("symbol"),
        "symbol": signal.get("symbol"),
        "direction": "LONG",
        "strategy_family": "CatalystContinuationLong",
        "mode": "OPENING_BURST_HYPER_LONG",
        "trigger": "OPENING_BURST_HYPER_LONG",
        "entry": entry,
        "limit_price": entry,
        "hard_max_entry_price": round(float(signal.get("entry_cap") or entry), 2),
        "stop": stop,
        "target_1": target_1,
        "target_2": round(float(candidate.get("target_2") or entry + ((entry - stop) * 2.25)), 2),
        "shares": shares,
        "notional_usd": round(shares * entry, 2),
        "max_risk_usd": round(max(entry - stop, 0.01) * shares, 2),
        "spread_bps": float(candidate.get("spread_bps") or signal.get("spread_bps") or 0.0),
        "max_slippage_bps": float(candidate.get("max_slippage_bps") or 20.0),
        "first_minute_volume": float(candidate.get("first_minute_volume") or 999999),
        "first_minute_dollar_volume": float(candidate.get("first_minute_dollar_volume") or 999999),
        "close_in_range_pct": float(candidate.get("close_in_range_pct") or 1.0),
        "opening_drive_reference_price": float(candidate.get("opening_drive_reference_price") or entry),
        "time_in_force": "DAY",
        "extended_hours": False,
        "order_type": "LIMIT",
        "force_flat_time": "15:45:00",
    }


class OpeningBurstExecutor:
    def __init__(self, router: OrderRouter | None = None, cfg: dict[str, Any] | None = None) -> None:
        self.router = router or OrderRouter(cfg=cfg)
        self.cfg = cfg or self.router.cfg

    def submit_signal(self, signal: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        guards = active_guards(self.cfg)
        if not guards.get("live_armed"):
            return {"ok": False, "reason": "live_armed_missing"}
        if guards.get("disable_entries"):
            return {"ok": False, "reason": "disable_entries_active"}
        if guards.get("kill_switch"):
            return {"ok": False, "reason": "kill_switch_active"}
        plan = build_opening_burst_plan(signal, candidate, self.cfg)
        ok, reason = validate_trade_plan(plan, risk_config_for_validation(self.cfg))
        if not ok:
            return {"ok": False, "reason": reason, "plan": plan}
        return self.router.submit_order(plan)
