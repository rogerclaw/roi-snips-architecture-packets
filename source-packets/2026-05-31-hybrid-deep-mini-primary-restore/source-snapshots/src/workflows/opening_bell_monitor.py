"""Opening-bell readiness and monitor entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from ..common.config import load_live_config, repo_root
from ..common.provider_factory import build_live_readiness_report, build_market_data_adapter
from ..research.trade_authorization_ticket import load_today_ticket, validate_ticket
from .deep_mini_bridge import DEEP_MINI_REQUIRED_BLOCKER
from .live_monitor import _bar_timestamp, _extract_quote_timestamp, _extract_quote_value, _mode_diagnostics


def load_opening_bell_config(path: str | Path | None = None) -> dict[str, Any]:
    resolved = Path(path) if path else repo_root() / "config" / "opening_bell.yaml"
    if not resolved.exists():
        return {"opening_bell": {"enabled": False, "reason": "config_missing"}}
    data = yaml.safe_load(resolved.read_text()) or {}
    return data if isinstance(data, dict) else {"opening_bell": {}}


def _latest_morning_packet(root: Path) -> dict[str, Any] | None:
    trade_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    path = root / "reports" / "morning" / "json" / f"{trade_date}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _candidate_rows(packet: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not packet:
        return []
    authorization = packet.get("trade_authorization") or {}
    if authorization:
        if authorization.get("authorized") is not True:
            return []
        authorized_symbol = str(authorization.get("ticker") or "").upper()
        best = packet.get("best_pick") or packet.get("best_pick_candidate") or {}
        if isinstance(best, dict):
            symbol = str(best.get("symbol") or best.get("ticker") or "").upper()
            return [best] if symbol == authorized_symbol else []
        if str(best or "").upper() == authorized_symbol:
            return [{"ticker": authorized_symbol}]
        return []
    rows: list[dict[str, Any]] = []
    best = packet.get("best_pick") or packet.get("best_pick_candidate") or {}
    if isinstance(best, dict):
        rows.append(best)
    elif best:
        rows.append({"_malformed": True, "raw_type": type(best).__name__})
    watchlist = packet.get("watchlist") or {}
    for tier in ["A", "B"]:
        for row in watchlist.get(tier) or []:
            rows.append(row if isinstance(row, dict) else {"_malformed": True, "raw_type": type(row).__name__})
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        if row.get("_malformed"):
            deduped.append(row)
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(row)
    return deduped[:3]


def _candidate_specific_readiness(packet: dict[str, Any] | None, cfg: dict[str, Any]) -> dict[str, Any]:
    rows = _candidate_rows(packet)
    if not rows:
        return {"ok": False, "reason": "no_primary_or_backup_candidates", "candidates": [], "blockers": ["no_primary_or_backup_candidates"]}
    md = build_market_data_adapter(cfg)
    data_cfg = ((load_opening_bell_config().get("opening_bell") or {}).get("data") or {})
    max_quote_age_ms = int(data_cfg.get("max_quote_age_ms", 1000))
    max_bar_age_seconds = int(data_cfg.get("max_bar_age_seconds", 90))
    now_utc = datetime.now(ZoneInfo("UTC"))
    trade_date = datetime.now(ZoneInfo("America/New_York")).date()
    blockers: list[str] = []
    out_rows: list[dict[str, Any]] = []
    seen_counts: dict[str, int] = {}
    for row in rows:
        if row.get("_malformed"):
            blockers.append("malformed_candidate_row")
            out_rows.append({"symbol": None, "blockers": ["malformed_candidate_row"], "raw_type": row.get("raw_type")})
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "").upper()
        seen_counts[symbol] = seen_counts.get(symbol, 0) + 1
        quote_res = md.get_quote(symbol)
        bars_res = md.get_bars_1m(symbol, limit=240)
        quote = quote_res.get("quote") or {}
        bars = bars_res.get("bars") or []
        quote_ts = _extract_quote_timestamp(quote)
        quote_age_ms = None
        if quote_ts is not None:
            quote_age_ms = int((now_utc - quote_ts.astimezone(ZoneInfo("UTC"))).total_seconds() * 1000)
        bar_timestamps = sorted(ts for bar in bars if (ts := _bar_timestamp(bar)) is not None)
        latest_bar_ts = bar_timestamps[-1] if bar_timestamps else None
        latest_bar_age_seconds = None
        if latest_bar_ts is not None:
            latest_bar_age_seconds = int((now_utc - latest_bar_ts.astimezone(ZoneInfo("UTC"))).total_seconds())
        bid = _extract_quote_value(quote, "bid")
        ask = _extract_quote_value(quote, "ask")
        last = _extract_quote_value(quote, "last", "price")
        spread_bps = quote.get("spread_bps")
        symbol_blockers: list[str] = []
        if not quote_res.get("ok"):
            symbol_blockers.append(str(quote_res.get("reason") or "quote_unavailable"))
        if not bars_res.get("ok"):
            symbol_blockers.append(str(bars_res.get("reason") or "bars_unavailable"))
        if bid is None or ask is None:
            symbol_blockers.append("bid_ask_missing")
        if last is None:
            symbol_blockers.append("last_price_missing")
        if not bars:
            symbol_blockers.append("bars_missing")
        if quote_ts is None:
            symbol_blockers.append("quote_timestamp_missing")
        else:
            quote_trade_date = quote_ts.astimezone(ZoneInfo("America/New_York")).date()
            if quote_trade_date != trade_date:
                symbol_blockers.append("quote_not_same_trade_date")
            if quote_age_ms is None or quote_age_ms > max_quote_age_ms:
                symbol_blockers.append("quote_stale")
        if bars and latest_bar_ts is None:
            symbol_blockers.append("bar_timestamp_missing")
        elif latest_bar_ts is not None:
            bar_trade_date = latest_bar_ts.astimezone(ZoneInfo("America/New_York")).date()
            if bar_trade_date != trade_date:
                symbol_blockers.append("bar_not_same_trade_date")
            if latest_bar_age_seconds is None or latest_bar_age_seconds > max_bar_age_seconds:
                symbol_blockers.append("bar_stale")
        mode = _mode_diagnostics({**row, "symbol": symbol, "spread_bps": spread_bps}, "ENTRY_WINDOW", quote, bars, cfg)
        if not any(not item.get("failed_predicates") for item in (mode.get("attempted_modes") or [])):
            symbol_blockers.append("no_immediately_available_entry_mode")
        out_rows.append(
            {
                "symbol": symbol,
                "quote_ok": bool(quote_res.get("ok")),
                "bars_ok": bool(bars_res.get("ok")),
                "quote_age_ms": quote_age_ms,
                "latest_bar_age_seconds": latest_bar_age_seconds,
                "bid": bid,
                "ask": ask,
                "last": last,
                "spread_bps": spread_bps,
                "bars_count": len(bars),
                "mode_availability": mode,
                "blockers": symbol_blockers,
            }
        )
        blockers.extend(f"{symbol}:{blocker}" for blocker in symbol_blockers)
    for symbol, count in seen_counts.items():
        if count > 1:
            blockers.append(f"{symbol}:duplicate_candidate_row")
    return {"ok": not blockers, "candidates": out_rows, "blockers": blockers}


def _packet_from_ticket(ticket: dict[str, Any] | None) -> dict[str, Any] | None:
    validation = validate_ticket(ticket)
    if not validation.valid:
        return None
    ticker = str((ticket or {}).get("authorized_ticker") or "").upper()
    return {
        "best_pick": {
            "ticker": ticker,
            "symbol": ticker,
            "authorized_strategy": (ticket or {}).get("authorized_strategy") or (ticket or {}).get("strategy"),
            "trade_authorization_ticket": ticket,
        },
        "trade_authorization": {"authorized": True, "ticker": ticker},
    }


def check_opening_bell_readiness(*, ignore_arm_guards: bool = False, inspect_broker_state: bool = True) -> dict[str, Any]:
    root = repo_root()
    live_cfg = load_live_config()
    opening_cfg = load_opening_bell_config()
    readiness = build_live_readiness_report(live_cfg, inspect_broker_state=inspect_broker_state)
    packet = _latest_morning_packet(root)
    ticket = load_today_ticket(root)
    ticket_validation = validate_ticket(ticket)
    blockers = list(readiness.get("execution_blockers") or [])
    ignored_blockers: list[str] = []
    if ignore_arm_guards:
        arm_guard_blockers = {"live_armed_missing", "disable_entries_active"}
        ignored_blockers = [item for item in blockers if item in arm_guard_blockers]
        blockers = [item for item in blockers if item not in arm_guard_blockers]
    opening_bell = opening_cfg.get("opening_bell") or {}
    if not opening_bell.get("enabled"):
        reason = str(opening_bell.get("reason") or "opening_bell_disabled")
        blockers.append("opening_bell_config_missing" if reason == "config_missing" else reason)
    status = "GREEN"
    if blockers:
        status = "YELLOW" if set(blockers).issubset({"live_armed_missing", "disable_entries_active"}) else "RED"
    env_live = os.getenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "").strip().lower() in {"1", "true", "yes", "on"}
    if status == "GREEN" and not env_live:
        status = "YELLOW"
        blockers.append("live_submission_env_missing")
    if status == "GREEN" and env_live and packet and packet.get("deep_mini_required_for_live_research"):
        if packet.get("deep_mini_shortlist_status") != "completed" or packet.get("deep_mini_completed_before_deadline") is not True:
            status = "RED"
            blockers.append(DEEP_MINI_REQUIRED_BLOCKER)
    if status == "GREEN" and env_live and not ticket_validation.valid:
        status = "RED"
        blockers.extend(ticket_validation.blockers)
    if status == "GREEN" and env_live and packet and (packet.get("deep_mini_required_for_live_research") or packet.get("trade_authorization")):
        authorization = (packet or {}).get("trade_authorization") or {}
        authorized = str(authorization.get("ticker") or "").upper()
        ticket_ticker = str((ticket or {}).get("authorized_ticker") or "").upper()
        if authorization.get("authorized") is not True or authorized != ticket_ticker:
            status = "RED"
            blockers.append("one_ticker_trade_authorization_missing_or_blocked")
    primary = None
    if packet:
        best = packet.get("best_pick") or packet.get("best_pick_candidate") or {}
        primary = (best.get("ticker") or best.get("symbol")) if isinstance(best, dict) else None
        authorization = packet.get("trade_authorization") or {}
        if authorization.get("authorized") is True:
            primary = authorization.get("ticker") or primary
    if ticket_validation.valid:
        primary = ticket.get("authorized_ticker") or primary
    candidate_readiness = {"ok": False, "reason": "skipped_until_generic_readiness_green"}
    if status == "GREEN":
        executable_packet = _packet_from_ticket(ticket) if env_live else packet
        candidate_readiness = _candidate_specific_readiness(executable_packet, live_cfg)
        candidate_blockers = list(candidate_readiness.get("blockers") or [])
        if candidate_blockers:
            status = "RED"
            blockers.extend(candidate_blockers)
    return {
        "status": status,
        "opening_bell_enabled": bool(opening_bell.get("enabled")),
        "primary_candidate": primary,
        "readiness": readiness,
        "candidate_specific_readiness": candidate_readiness,
        "opening_bell_blockers": sorted(set(blockers)),
        "ignored_arm_guard_blockers": sorted(set(ignored_blockers)),
        "ticket_valid": ticket_validation.valid,
        "ticket_status": ticket_validation.status,
        "ticket_blockers": ticket_validation.blockers,
        "message": {
            "GREEN": "opening-bell autonomous trading armed",
            "YELLOW": "research only / no live order",
            "RED": "hard block / no live order",
        }[status],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Roi Snips opening-bell monitor/readiness")
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument(
        "--ignore-arm-guards",
        action="store_true",
        help="Evaluate candidate/data readiness as the conditional arming gate, ignoring only live_armed_missing and disable_entries_active.",
    )
    parser.add_argument(
        "--skip-broker-state",
        action="store_true",
        help="Do not inspect live broker account, orders, or positions; report as not execution-ready.",
    )
    args = parser.parse_args()
    result = check_opening_bell_readiness(ignore_arm_guards=args.ignore_arm_guards, inspect_broker_state=not args.skip_broker_state)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if result["status"] == "GREEN" else 1)


if __name__ == "__main__":
    main()
