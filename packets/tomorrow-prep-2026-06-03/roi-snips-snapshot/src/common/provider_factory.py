from __future__ import annotations

import os
from typing import Any

from ..adapters.alpaca_market_data import AlpacaMarketDataAdapter
from ..adapters.alpaca_trade import AlpacaTradeAdapter
from ..adapters.webull_md import WebullMarketDataAdapter
from ..adapters.webull_trade import WebullTradeAdapter
from .config import load_live_config
from .runtime_state import active_guards, session_phase


def configured_market_data_provider(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_live_config()
    return str(((cfg.get("market_data") or {}).get("provider") or "alpaca")).strip().lower()


def configured_broker_provider(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_live_config()
    return str(((cfg.get("broker") or {}).get("provider") or "alpaca")).strip().lower()


def build_market_data_adapter(cfg: dict[str, Any] | None = None, provider: str | None = None) -> Any:
    resolved = (provider or configured_market_data_provider(cfg)).strip().lower()
    if resolved == "webull":
        return WebullMarketDataAdapter()
    return AlpacaMarketDataAdapter()


def build_trade_adapter(cfg: dict[str, Any] | None = None, provider: str | None = None) -> Any:
    resolved = (provider or configured_broker_provider(cfg)).strip().lower()
    if resolved == "webull":
        return WebullTradeAdapter()
    return AlpacaTradeAdapter()


def _boolish(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in {"0", "false", "none", "null", "nan"}


def _adapter_runtime_environment(adapter: Any) -> dict[str, Any]:
    if hasattr(adapter, "runtime_environment"):
        try:
            value = adapter.runtime_environment()
            if isinstance(value, dict):
                return value
        except Exception:
            return {"provider": adapter.__class__.__name__.lower(), "runtime_environment_error": True}
    return {"provider": adapter.__class__.__name__.lower()}


def _classify_market_data_blockers(md_health: dict[str, Any], execution_blockers: list[str]) -> None:
    reason = str(((md_health.get("quote") or {}).get("reason") or md_health.get("reason") or "")).lower()
    if "subscription does not permit querying recent sip data" in reason:
        execution_blockers.append("market_data_entitlement_missing:sip_recent_quotes")
    elif "subscription" in reason and "permit" in reason:
        execution_blockers.append("market_data_entitlement_missing")


def _classify_broker_drift(cfg: dict[str, Any], broker_runtime: dict[str, Any], execution_blockers: list[str]) -> None:
    broker_cfg = cfg.get("broker") or {}
    expected = str(broker_cfg.get("environment") or "").strip().lower()
    actual = str(broker_runtime.get("environment") or "").strip().lower()
    if expected and actual and expected != actual:
        execution_blockers.append(f"broker_environment_mismatch:{expected}!={actual}")

    configured_base = str(broker_cfg.get("base_url") or "").strip().rstrip("/")
    runtime_base = str(broker_runtime.get("base_url") or "").strip().rstrip("/")
    if configured_base and runtime_base and configured_base != runtime_base:
        execution_blockers.append("broker_base_url_mismatch")

    live_arm = os.getenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
    paper_arm = os.getenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
    if live_arm and actual == "paper":
        execution_blockers.append("live_submission_requires_live_broker")
    if paper_arm and actual == "live":
        execution_blockers.append("paper_submission_requires_paper_broker")


def build_live_readiness_report(
    cfg: dict[str, Any] | None = None,
    *,
    probe_symbol: str = "SPY",
    market_data_provider: str | None = None,
    broker_provider: str | None = None,
    inspect_broker_state: bool = True,
) -> dict[str, Any]:
    cfg = cfg or load_live_config()
    md_provider = (market_data_provider or configured_market_data_provider(cfg)).strip().lower()
    broker = (broker_provider or configured_broker_provider(cfg)).strip().lower()
    guards = active_guards(cfg)
    phase = session_phase(cfg)
    md = build_market_data_adapter(cfg, provider=md_provider)
    trade = build_trade_adapter(cfg, provider=broker)

    md_health = md.healthcheck(probe_symbol) if hasattr(md, "healthcheck") else {"ok": False, "reason": "healthcheck_not_supported"}
    if inspect_broker_state:
        trade_health = trade.healthcheck() if hasattr(trade, "healthcheck") else {"ok": False, "reason": "healthcheck_not_supported"}
    else:
        trade_health = {"ok": True, "skipped": True, "reason": "broker_state_inspection_skipped"}

    market_cfg = cfg.get("market_data") or {}
    broker_runtime = _adapter_runtime_environment(trade)
    market_runtime = _adapter_runtime_environment(md)
    quote = ((md_health.get("quote") or {}).get("quote") or {}) if isinstance(md_health, dict) else {}
    bid = quote.get("bid") if isinstance(quote, dict) else None
    ask = quote.get("ask") if isinstance(quote, dict) else None
    last = quote.get("last") if isinstance(quote, dict) else None
    execution_blockers: list[str] = []

    controls_cfg = cfg.get("controls") or {}
    if _boolish(controls_cfg.get("require_live_armed_for_entries", True)) and not guards.get("live_armed"):
        execution_blockers.append("live_armed_missing")
    if guards.get("kill_switch"):
        execution_blockers.append("kill_switch_active")
    if guards.get("disable_entries"):
        execution_blockers.append("disable_entries_active")
    if not md_health.get("ok"):
        execution_blockers.append(md_health.get("reason") or "market_data_unhealthy")
    if not trade_health.get("ok"):
        execution_blockers.append(trade_health.get("reason") or "broker_unhealthy")
    _classify_market_data_blockers(md_health, execution_blockers)
    _classify_broker_drift(cfg, broker_runtime, execution_blockers)
    if _boolish(market_cfg.get("require_bid_ask", True)) and (not _boolish(bid) or not _boolish(ask)):
        execution_blockers.append("bid_ask_missing_for_execution")
    if _boolish(market_cfg.get("require_prior_close", True)) and not _boolish(quote.get("prev_close")):
        execution_blockers.append("prior_close_missing_for_execution")
    if not _boolish(last):
        execution_blockers.append("last_price_missing_for_execution")
    broker_health = trade_health if isinstance(trade_health, dict) else {}
    open_orders = ((broker_health.get("open_orders") or {}).get("orders") or []) if isinstance(broker_health.get("open_orders"), dict) else []
    if open_orders:
        execution_blockers.append("existing_position_or_order_blocker:open_orders")
    positions_res = None
    if inspect_broker_state and hasattr(trade, "list_positions"):
        try:
            positions_res = trade.list_positions()
        except Exception as exc:
            positions_res = {"ok": False, "reason": f"positions_unavailable:{exc}"}
    elif not inspect_broker_state:
        positions_res = {"ok": True, "skipped": True, "positions": []}
    positions = (positions_res or {}).get("positions") or []
    positive_positions = []
    for row in positions:
        try:
            qty = float(row.get("qty") or row.get("quantity") or row.get("position") or 0)
        except Exception:
            qty = 0.0
        if qty > 0:
            positive_positions.append(row)
    if positive_positions:
        execution_blockers.append("existing_position_or_order_blocker:positions")
    if not inspect_broker_state:
        execution_blockers.append("broker_state_inspection_skipped")

    feed_requirement = str(market_cfg.get("required_feed_for_full_mode") or "").strip().lower()
    actual_feed = str(md_health.get("feed") or ((md_health.get("quote") or {}).get("feed") or "")).strip().lower()
    if feed_requirement and actual_feed and feed_requirement != actual_feed:
        execution_blockers.append(f"feed_requirement_mismatch:{feed_requirement}!={actual_feed}")

    full_execution_ready = md_health.get("ok") and trade_health.get("ok") and not execution_blockers
    return {
        "ok": full_execution_ready,
        "probe_symbol": probe_symbol,
        "market_data_provider": md_provider,
        "broker_provider": broker,
        "market_data_runtime": market_runtime,
        "broker_runtime": broker_runtime,
        "runtime_guards": guards,
        "session_phase": phase,
        "market_data_health": md_health,
        "broker_health": trade_health,
        "position_state": {"ok": (positions_res or {}).get("ok", True), "positions": positions, "positive_position_count": len(positive_positions)},
        "execution_blockers": execution_blockers,
        "full_execution_ready": full_execution_ready,
    }
