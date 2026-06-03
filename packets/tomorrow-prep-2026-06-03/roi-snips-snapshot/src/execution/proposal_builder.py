"""Proposal packet builder for playbook-aligned Opening-Drive v2."""

from __future__ import annotations

import math
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Any


def _round_price(value: float) -> float:
    return round(float(value), 2)


def _positive_number(value: Any, field: str) -> float:
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError(f"invalid_trade_plan_{field}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"invalid_trade_plan_{field}")
    return parsed


def size_position(entry: float, stop: float, risk_budget_usd: float, notional_cap_usd: float) -> tuple[int, float, float]:
    risk_per_share = max(entry - stop, 0.01)
    shares_by_risk = max(int(math.floor(risk_budget_usd / risk_per_share)), 1)
    shares_by_notional = max(int(math.floor(notional_cap_usd / entry)), 1)
    shares = max(1, min(shares_by_risk, shares_by_notional))
    notional = shares * entry
    risk = shares * risk_per_share
    return shares, round(notional, 2), round(risk, 2)


def build_trade_proposal(candidate: dict[str, Any]) -> dict[str, Any]:
    plan_id = f"plan_{uuid.uuid4().hex[:10]}"
    entry = _round_price(_positive_number(candidate["entry"], "entry"))
    stop = _round_price(_positive_number(candidate["stop"], "stop"))
    target_1 = _round_price(_positive_number(candidate["target_1"], "target_1"))
    target_2 = _round_price(candidate.get("target_2", entry + ((entry - stop) * 2.0)))
    stretch_target = _round_price(candidate.get("stretch_target", entry + ((entry - stop) * 3.0)))
    shares = int(candidate["shares"])
    notional = round(float(candidate["notional_usd"]), 2)
    risk = round(float(candidate["max_risk_usd"]), 2)
    if stop >= entry:
        raise ValueError("invalid_trade_plan_stop_must_be_below_entry")
    if target_1 <= entry or target_2 <= entry or stretch_target <= entry:
        raise ValueError("invalid_trade_plan_targets_must_exceed_entry")
    if shares <= 0 or notional <= 0 or risk <= 0:
        raise ValueError("invalid_trade_plan_size_or_risk")
    execution_command = f"EXECUTE ENTRY {plan_id}"
    trigger = str(candidate.get("trigger") or "VWAP_RECLAIM").upper()
    mode = str(candidate.get("mode") or trigger).upper()
    bucket = candidate.get("setup_bucket") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    cid_raw = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}|{candidate.get('ticker')}|{mode}|{candidate.get('trigger')}|{bucket}|BUY"
    client_order_id = hashlib.sha256(cid_raw.encode("utf-8")).hexdigest()[:32]

    return {
        "plan_id": plan_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "trade_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ticker": candidate.get("ticker"),
        "symbol": candidate.get("ticker"),
        "direction": "LONG",
        "mode": mode,
        "strategy_family": candidate.get("strategy_family", "CatalystContinuationLong"),
        "trigger": trigger,
        "thesis": candidate.get("thesis") or candidate.get("catalyst_summary", "catalyst-backed continuation setup"),
        "catalyst_summary": candidate.get("catalyst_summary", "official_and_structured_sources_required"),
        "catalyst_type": candidate.get("catalyst_type"),
        "hype_driver": candidate.get("hype_driver"),
        "research_conviction_score": int(candidate.get("research_conviction_score", 0)),
        "attention_ignition_score": int(candidate.get("attention_ignition_score", 0)),
        "pre_move_asymmetry_score": int(candidate.get("pre_move_asymmetry_score", 0)),
        "execution_safety_score": int(candidate.get("execution_safety_score", 0)),
        "live_validation_score": int(candidate.get("live_validation_score", 0)),
        "entry": entry,
        "stop": stop,
        "initial_stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "stretch_target": stretch_target,
        "shares": shares,
        "qty": str(shares),
        "notional_usd": notional,
        "planned_notional_usd": notional,
        "notional": str(notional),
        "max_risk_usd": risk,
        "risk_per_share": round(entry - stop, 4),
        "spread_bps": round(float(candidate.get("spread_bps", 0.0)), 3),
        "max_slippage_bps": round(float(candidate.get("max_slippage_bps", 20.0)), 3),
        "why_tradeable": candidate.get("why_tradeable", "catalyst_and_liquidity_gates_passed"),
        "why_might_fail": candidate.get("why_might_fail", "failed_follow_through_or_vwap_loss"),
        "no_trade_if": candidate.get("no_trade_if", []),
        "thesis_failure_conditions": candidate.get("thesis_failure_conditions", candidate.get("no_trade_if", [])),
        "execution_command": execution_command,
        "status": "ready_for_execution",
        "open_positions": int(candidate.get("open_positions", 0)),
        "order_type": candidate.get("order_type", "LIMIT"),
        "limit_price": _round_price(candidate.get("limit_price", entry)),
        "time_in_force": candidate.get("time_in_force", "DAY"),
        "extended_hours": bool(candidate.get("extended_hours", False)),
        "alpaca_order_route": candidate.get("alpaca_order_route"),
        "hard_max_entry_price": _round_price(candidate.get("hard_max_entry_price", candidate.get("limit_price", entry))),
        "time_stop": candidate.get("time_stop", "11:00:00"),
        "force_flat_time": candidate.get("force_flat_time", "15:45:00"),
        "opening_drive_reference_price": candidate.get("opening_drive_reference_price"),
        "first_minute_volume": candidate.get("first_minute_volume"),
        "first_minute_dollar_volume": candidate.get("first_minute_dollar_volume"),
        "close_in_range_pct": candidate.get("close_in_range_pct"),
        "subminute_signal": bool(candidate.get("subminute_signal", False)),
        "subminute_quote_samples": candidate.get("subminute_quote_samples"),
        "subminute_elapsed_seconds": candidate.get("subminute_elapsed_seconds"),
        "opening_exit_manager_armed": bool(candidate.get("opening_exit_manager_armed", False)),
        "add_allowed": bool(candidate.get("add_allowed", False)),
        "average_down_allowed": False,
        "client_order_id": client_order_id,
        "vetoes_checked": candidate.get("vetoes_checked", []),
        "data_sources": candidate.get("data_sources", []),
        "signal_context": candidate.get("signal_context", {}),
    }
