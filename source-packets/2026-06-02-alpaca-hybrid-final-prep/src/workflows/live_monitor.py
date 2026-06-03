"""Autonomous broker-aware live monitor for the unified v5 runtime."""

from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..common.config import load_live_config, risk_config_for_validation
from ..common.provider_factory import build_market_data_adapter, configured_market_data_provider
from ..common.runtime_state import active_guards, session_phase, should_force_flat
from ..common.telegram import TelegramNotifier
from ..execution.audit_logger import append_audit_event
from ..execution.order_router import OrderRouter
from ..execution.position_manager import PositionManager
from ..execution.proposal_builder import build_trade_proposal, size_position
from ..execution.proposal_store import find_recent_matching_proposal, save_proposal
from ..research import lifecycle as lc
from ..research.trade_authorization_ticket import (
    load_today_ticket,
    ticket_authorizes_symbol,
    validate_submission_against_ticket,
    validate_ticket,
)
from ..risk.rules import validate_trade_plan
from ..strategy.second_leg_continuation import evaluate_second_leg_continuation


def _load_authorized_trade_ticket(repo_root: Path) -> dict[str, Any] | None:
    return load_today_ticket(repo_root)


def _load_active_watchlist(repo_root: Path) -> list[dict[str, Any]]:
    ticket = _load_authorized_trade_ticket(repo_root)
    ticket_validation = validate_ticket(ticket)
    if not ticket_validation.valid:
        return []
    ticker = str((ticket or {}).get("authorized_ticker") or "").upper()
    return [
        {
            "symbol": ticker,
            "ticker": ticker,
            "authorized_strategy": ticket.get("authorized_strategy") or ticket.get("strategy"),
            "trade_authorization_ticket": ticket,
        }
    ]


def _validate_ticket_for_submission(proposal: dict[str, Any], ticket: dict[str, Any] | None) -> tuple[bool, str | None]:
    return validate_submission_against_ticket(proposal, ticket)


def _bar_timestamp(bar: dict[str, Any]) -> datetime | None:
    raw = bar.get("timestamp") or bar.get("ts") or bar.get("time") or bar.get("datetime")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            value = float(raw)
            if value > 10_000_000_000:
                value /= 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        text = str(raw)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


def _bar_float(bar: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in bar:
            try:
                return float(bar[key])
            except Exception:
                continue
    return None


def _extract_quote_value(quote: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in quote:
            try:
                return float(quote[key])
            except Exception:
                continue
    return None


def _extract_quote_timestamp(quote: dict[str, Any]) -> datetime | None:
    raw = quote.get("timestamp") or quote.get("ts") or quote.get("quote_time") or quote.get("quoteTime")
    if raw is None:
        return None
    return _bar_timestamp({"timestamp": raw})


def _session_rows(
    bars: list[dict[str, Any]],
    tz_name: str,
    include_premarket: bool = False,
    session_date: Any | None = None,
) -> list[tuple[datetime, dict[str, Any]]]:
    tz = ZoneInfo(tz_name)
    out: list[tuple[datetime, dict[str, Any]]] = []
    for bar in bars:
        ts = _bar_timestamp(bar)
        if not ts:
            continue
        local = ts.astimezone(tz)
        if session_date is not None and local.date() != session_date:
            continue
        if include_premarket:
            if time(4, 0) <= local.time() < time(9, 30):
                out.append((local, bar))
        else:
            if local.time() >= time(9, 30):
                out.append((local, bar))
    return sorted(out, key=lambda row: row[0])


def _compute_vwap(rows: list[tuple[datetime, dict[str, Any]]]) -> list[float]:
    running_pv = 0.0
    running_vol = 0.0
    out = []
    for _, bar in rows:
        high = _bar_float(bar, "high", "h") or 0.0
        low = _bar_float(bar, "low", "l") or 0.0
        close = _bar_float(bar, "close", "c", "last") or 0.0
        vol = _bar_float(bar, "volume", "v", "vol") or 0.0
        typical = (high + low + close) / 3 if high and low and close else close
        running_pv += typical * vol
        running_vol += vol
        out.append((running_pv / running_vol) if running_vol else close)
    return out


def _opening_drive_state_path(repo_root: Path) -> Path:
    return repo_root / "state" / "opening_drive_subminute_state.json"


def _load_opening_drive_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_opening_drive_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _opening_drive_bucket(local_dt: datetime) -> str:
    return local_dt.strftime("%Y-%m-%dT%H:%M")


def _sample_quote(quote: dict[str, Any]) -> dict[str, Any] | None:
    ts = _extract_quote_timestamp(quote)
    last = _extract_quote_value(quote, "last", "price")
    if ts is None or last is None:
        return None
    return {
        "timestamp": ts.astimezone(timezone.utc).isoformat(),
        "last": float(last),
        "bid": _extract_quote_value(quote, "bid"),
        "ask": _extract_quote_value(quote, "ask"),
        "spread_bps": _extract_quote_value(quote, "spread_bps"),
    }


def _update_opening_drive_tape(state: dict[str, Any], symbol: str, quote: dict[str, Any], local_dt: datetime, max_samples: int = 60) -> tuple[dict[str, Any], dict[str, Any]]:
    sample = _sample_quote(quote)
    bucket = _opening_drive_bucket(local_dt)
    fresh: dict[str, Any] = {}
    for key, value in (state or {}).items():
        if isinstance(value, dict) and value.get("bucket") == bucket:
            fresh[key] = value

    tape = fresh.get(symbol)
    if not isinstance(tape, dict) or tape.get("bucket") != bucket:
        tape = {"bucket": bucket, "samples": []}

    samples = list(tape.get("samples") or [])
    if sample is not None:
        if not samples or samples[-1].get("timestamp") != sample["timestamp"] or samples[-1].get("last") != sample["last"]:
            samples.append(sample)
        else:
            samples[-1] = sample
    tape["samples"] = samples[-max(1, int(max_samples)):]
    fresh[symbol] = tape
    return fresh, tape


def _project_first_minute_metric(value: float, elapsed_seconds: float) -> float:
    if value <= 0 or elapsed_seconds <= 0:
        return 0.0
    return value * (60.0 / elapsed_seconds)


def _parse_clock(value: str, default: str) -> time:
    raw = str(value or default)
    parts = [int(part) for part in raw.split(":")]
    if len(parts) == 2:
        return time(parts[0], parts[1], 0)
    return time(parts[0], parts[1], parts[2])


def _in_clock_window(current: time, start: str, end: str) -> bool:
    return _parse_clock(start, start) <= current <= _parse_clock(end, end)


def _close_in_range_pct(close: float, low: float, high: float) -> float:
    spread = max(high - low, 0.0)
    if spread <= 0:
        return 0.5
    return max(0.0, min(1.0, (close - low) / spread))


def _opening_range(rows: list[tuple[datetime, dict[str, Any]]], bars_count: int = 5) -> dict[str, float] | None:
    first = rows[:bars_count]
    if len(first) < bars_count:
        return None
    highs = [_bar_float(bar, "high", "h") for _, bar in first]
    lows = [_bar_float(bar, "low", "l") for _, bar in first]
    highs_f = [v for v in highs if v is not None]
    lows_f = [v for v in lows if v is not None]
    if not highs_f or not lows_f:
        return None
    return {"high": max(highs_f), "low": min(lows_f)}


def _volume_confirmation(volumes: list[float], multiplier: float = 1.2) -> bool:
    if len(volumes) < 6:
        return False
    last = volumes[-1]
    baseline = sum(volumes[-6:-1]) / 5
    return baseline > 0 and last >= baseline * multiplier


def _proposal_alert_text(proposal: dict[str, Any]) -> str:
    return (
        f"Roi Snips live candidate\n"
        f"plan_id: {proposal['plan_id']}\n"
        f"ticker: {proposal['ticker']}\n"
        f"mode: {proposal.get('mode')}\n"
        f"trigger: {proposal['trigger']}\n"
        f"entry: {proposal['entry']}\n"
        f"stop: {proposal['stop']}\n"
        f"target_1: {proposal['target_1']}\n"
        f"shares: {proposal['shares']}\n"
        f"notional_usd: {proposal['notional_usd']}"
    )


def _build_structured_candidate(symbol_row: dict[str, Any], phase: str, quote: dict[str, Any], bars: list[dict[str, Any]], cfg: dict[str, Any], open_positions: int) -> dict[str, Any] | None:
    risk = cfg.get("risk") or {}
    session = cfg.get("session") or cfg.get("schedule") or {}
    strategy = cfg.get("strategy") or {}
    opening_drive_cfg = strategy.get("opening_drive") or {}
    subminute_cfg = opening_drive_cfg.get("subminute") or {}
    tape = symbol_row.get("_opening_drive_tape") or {}
    last = _extract_quote_value(quote, "last", "price")
    if last is None:
        return None

    tz_name = session.get("timezone", "America/New_York")
    quote_ts = _extract_quote_timestamp(quote)
    quote_local_dt = quote_ts.astimezone(ZoneInfo(tz_name)) if quote_ts else None
    session_date = quote_local_dt.date() if quote_local_dt else None
    regular_rows = _session_rows(bars, tz_name, include_premarket=False, session_date=session_date)
    premarket_rows = _session_rows(bars, tz_name, include_premarket=True, session_date=session_date)
    premarket_highs = [(_bar_float(bar, "high", "h") or 0.0) for _, bar in premarket_rows]
    premarket_lows = [(_bar_float(bar, "low", "l") or 0.0) for _, bar in premarket_rows]
    premarket_high = max(premarket_highs) if premarket_highs else float(symbol_row.get("premarket_high") or last)
    premarket_low = min([v for v in premarket_lows if v > 0]) if any(v > 0 for v in premarket_lows) else float(symbol_row.get("premarket_low") or max(last * 0.97, 0.01))

    spread_bps = float(symbol_row.get("spread_bps") or quote.get("spread_bps") or 0.0)
    latest_local_dt = quote_local_dt if quote_ts else (regular_rows[-1][0] if regular_rows else None)
    latest_local_time = latest_local_dt.time() if latest_local_dt else time(0, 0)

    if opening_drive_cfg.get("enabled", True) and subminute_cfg.get("enabled", True) and latest_local_dt:
        subminute_end = subminute_cfg.get("entry_cutoff_et", subminute_cfg.get("entry_end_et", "09:30:55"))
        if _in_clock_window(latest_local_time, opening_drive_cfg.get("entry_start_et", "09:30:00"), subminute_end):
            samples = list(tape.get("samples") or [])
            min_samples = int(subminute_cfg.get("min_quote_samples", 3))
            min_elapsed_seconds = float(subminute_cfg.get("min_elapsed_seconds", 10))
            if len(samples) >= min_samples:
                sample_prices = [float(sample.get("last") or 0.0) for sample in samples if float(sample.get("last") or 0.0) > 0]
                sample_spreads = [float(sample.get("spread_bps") or 0.0) for sample in samples if sample.get("spread_bps") is not None]
                first_sample_ts = _bar_timestamp({"timestamp": samples[0].get("timestamp")})
                last_sample_ts = _bar_timestamp({"timestamp": samples[-1].get("timestamp")})
                elapsed_seconds = (last_sample_ts - first_sample_ts).total_seconds() if first_sample_ts and last_sample_ts else 0.0
                if len(sample_prices) >= min_samples and elapsed_seconds >= min_elapsed_seconds:
                    high_sample = max(sample_prices)
                    low_sample = min(sample_prices)
                    close_quality = _close_in_range_pct(last, low_sample, high_sample)
                    pullback_from_high_pct = ((high_sample - last) / high_sample) * 100.0 if high_sample > 0 else 100.0
                    push_from_first_sample_pct = ((last / sample_prices[0]) - 1.0) * 100.0 if sample_prices[0] > 0 else 0.0
                    reference_price = premarket_high if opening_drive_cfg.get("require_premarket_reference", True) else max(premarket_high, sample_prices[0])
                    break_above_reference_bps = ((last / max(reference_price, 0.01)) - 1.0) * 10000.0
                    max_chase_pct = float(risk.get("opening_drive_max_chase_pct", opening_drive_cfg.get("max_chase_pct_above_reference", 1.0)))
                    max_spread_bps = float(risk.get("opening_drive_max_spread_bps", opening_drive_cfg.get("max_spread_bps", risk.get("max_spread_bps", 60))))
                    avg_spread_bps = sum(sample_spreads) / len(sample_spreads) if sample_spreads else spread_bps

                    partial_bar = regular_rows[0][1] if regular_rows and regular_rows[0][0].hour == 9 and regular_rows[0][0].minute == 30 else None
                    partial_volume = _bar_float(partial_bar or {}, "volume", "v", "vol") or 0.0
                    partial_close = _bar_float(partial_bar or {}, "close", "c", "last") or last
                    session_open_dt = latest_local_dt.replace(hour=9, minute=30, second=0, microsecond=0)
                    elapsed_from_open_seconds = max((latest_local_dt - session_open_dt).total_seconds(), 1.0)
                    projected_volume = _project_first_minute_metric(partial_volume, elapsed_from_open_seconds)
                    projected_dollar_volume = _project_first_minute_metric(partial_volume * partial_close, elapsed_from_open_seconds)

                    subminute_ok = all(
                        [
                            projected_volume >= float(subminute_cfg.get("min_projected_first_minute_volume", risk.get("opening_drive_min_first_minute_volume", opening_drive_cfg.get("min_first_minute_volume", 0)))),
                            projected_dollar_volume >= float(subminute_cfg.get("min_projected_first_minute_dollar_volume", risk.get("opening_drive_min_first_minute_dollar_volume", opening_drive_cfg.get("min_first_minute_dollar_volume", 0)))),
                            close_quality >= float(subminute_cfg.get("min_close_in_range_pct", 0.75)),
                            pullback_from_high_pct <= float(subminute_cfg.get("max_pullback_from_high_pct", 0.35)),
                            push_from_first_sample_pct >= float(subminute_cfg.get("min_push_from_first_sample_pct", 0.15)),
                            break_above_reference_bps >= float(subminute_cfg.get("min_break_above_reference_bps", 5.0)),
                            spread_bps <= max_spread_bps,
                            avg_spread_bps <= max_spread_bps,
                            last >= high_sample * float(subminute_cfg.get("min_hold_pct_of_subminute_high", 0.9975)),
                        ]
                    )

                    if subminute_ok:
                        entry = round(max(last, reference_price + 0.01), 2)
                        stop = round(min(low_sample, reference_price * 0.995), 2)
                        hard_max_entry = round(reference_price * (1.0 + (max_chase_pct / 100.0)), 2)
                        if stop < entry <= hard_max_entry:
                            shares, notional, max_risk = size_position(
                                entry=entry,
                                stop=stop,
                                risk_budget_usd=float(risk.get("opening_drive_max_trade_risk_usd", opening_drive_cfg.get("risk_budget_usd", risk.get("max_trade_risk_usd", 80)))),
                                notional_cap_usd=float(risk.get("opening_drive_notional_usd_max", opening_drive_cfg.get("notional_cap_usd", risk.get("initial_notional_usd_max", 50)))),
                            )
                            if notional >= float(risk.get("initial_notional_usd_min", 50)):
                                risk_per_share = max(entry - stop, 0.01)
                                return {
                                    "ticker": symbol_row["symbol"],
                                    "mode": "OPENING_DRIVE_LONG",
                                    "trigger": "OPENING_DRIVE_LONG",
                                    "strategy_family": "CatalystContinuationLong",
                                    "catalyst_type": symbol_row.get("catalyst_type"),
                                    "catalyst_summary": f"{symbol_row.get('catalyst_type')} | {', '.join(symbol_row.get('catalyst_notes') or [])}",
                                    "thesis": symbol_row.get("why_tradeable") or "sub-minute opening-drive continuation on a catalyst-backed name",
                                    "entry": entry,
                                    "stop": stop,
                                    "target_1": round(entry + (risk_per_share * 1.5), 2),
                                    "target_2": round(entry + (risk_per_share * 2.25), 2),
                                    "shares": shares,
                                    "notional_usd": notional,
                                    "max_risk_usd": max_risk,
                                    "spread_bps": spread_bps,
                                    "max_slippage_bps": float(risk.get("opening_drive_max_slippage_bps", opening_drive_cfg.get("max_slippage_bps", 18))),
                                    "why_tradeable": symbol_row.get("why_tradeable"),
                                    "why_might_fail": symbol_row.get("why_might_fail") or "sub-minute opening-drive fades, projected first-minute volume collapses, or premarket high fails",
                                    "no_trade_if": list(symbol_row.get("hard_no_trade_conditions") or []) + [
                                        "sub-minute high is lost immediately",
                                        "projected first-minute volume deteriorates",
                                        "spread blows out",
                                    ],
                                    "open_positions": open_positions,
                                    "limit_price": round(entry, 2),
                                    "hard_max_entry_price": hard_max_entry,
                                    "time_in_force": "DAY",
                                    "extended_hours": False,
                                    "order_type": "LIMIT",
                                    "time_stop": opening_drive_cfg.get("time_stop_et", "09:45:00"),
                                    "force_flat_time": "15:45:00",
                                    "opening_drive_reference_price": round(reference_price, 4),
                                    "first_minute_volume": round(projected_volume, 2),
                                    "first_minute_dollar_volume": round(projected_dollar_volume, 2),
                                    "close_in_range_pct": round(close_quality, 4),
                                    "subminute_signal": True,
                                    "subminute_quote_samples": len(samples),
                                    "subminute_elapsed_seconds": round(elapsed_seconds, 2),
                                    "research_conviction_score": int(symbol_row.get("research_conviction_score", 0)),
                                    "attention_ignition_score": int(symbol_row.get("attention_ignition_score", 0)),
                                    "pre_move_asymmetry_score": int(symbol_row.get("pre_move_asymmetry_score", 0)),
                                    "execution_safety_score": int(symbol_row.get("execution_safety_score", 0)),
                                    "live_validation_score": int(symbol_row.get("live_validation_score", 0)),
                                    "opening_exit_manager_armed": True,
                                    "data_sources": [f"{configured_market_data_provider(cfg)}_market_data", "alpaca_news", "sec_edgar", "benzinga", "reddit", "x_optional"],
                                    "signal_context": {
                                        "phase": phase,
                                        "premarket_high": premarket_high,
                                        "premarket_low": premarket_low,
                                        "opening_drive_reference_price": reference_price,
                                        "subminute_high": high_sample,
                                        "subminute_low": low_sample,
                                        "avg_spread_bps": round(avg_spread_bps, 4),
                                        "break_above_reference_bps": round(break_above_reference_bps, 2),
                                        "push_from_first_sample_pct": round(push_from_first_sample_pct, 4),
                                        "pullback_from_high_pct": round(pullback_from_high_pct, 4),
                                        "projected_first_minute_volume": round(projected_volume, 2),
                                        "projected_first_minute_dollar_volume": round(projected_dollar_volume, 2),
                                    },
                                }

    if opening_drive_cfg.get("enabled", True) and regular_rows:
        min_regular_bars = int(opening_drive_cfg.get("min_regular_bars", 1))
        if len(regular_rows) >= min_regular_bars and _in_clock_window(latest_local_time, opening_drive_cfg.get("entry_start_et", "09:30:00"), opening_drive_cfg.get("entry_cutoff_et", "09:34:59")):
            first_bar = regular_rows[0][1]
            first_open = _bar_float(first_bar, "open", "o") or last
            first_high = _bar_float(first_bar, "high", "h") or last
            first_low = _bar_float(first_bar, "low", "l") or last
            first_close = _bar_float(first_bar, "close", "c", "last") or last
            first_volume = _bar_float(first_bar, "volume", "v", "vol") or 0.0
            first_dollar_volume = first_close * first_volume
            close_quality = _close_in_range_pct(first_close, first_low, first_high)
            vwap_values = _compute_vwap(regular_rows)
            latest_vwap = vwap_values[-1] if vwap_values else last
            reference_price = premarket_high if opening_drive_cfg.get("require_premarket_reference", True) else max(premarket_high, first_open)
            chase_pct = ((last / max(reference_price, 0.01)) - 1.0) * 100.0
            max_chase_pct = float(risk.get("opening_drive_max_chase_pct", opening_drive_cfg.get("max_chase_pct_above_reference", 1.0)))
            max_spread_bps = float(risk.get("opening_drive_max_spread_bps", opening_drive_cfg.get("max_spread_bps", risk.get("max_spread_bps", 60))))

            opening_drive_ok = all(
                [
                    first_volume >= float(risk.get("opening_drive_min_first_minute_volume", opening_drive_cfg.get("min_first_minute_volume", 0))),
                    first_dollar_volume >= float(risk.get("opening_drive_min_first_minute_dollar_volume", opening_drive_cfg.get("min_first_minute_dollar_volume", 0))),
                    close_quality >= float(risk.get("opening_drive_min_close_in_range_pct", opening_drive_cfg.get("min_close_in_range_pct", 0.0))),
                    spread_bps <= max_spread_bps,
                    last >= max(first_close, latest_vwap, reference_price),
                    chase_pct <= max_chase_pct,
                ]
            )

            if opening_drive_ok:
                entry = round(max(last, reference_price + 0.01), 2)
                stop = round(min(first_low, reference_price * 0.995), 2)
                hard_max_entry = round(reference_price * (1.0 + (max_chase_pct / 100.0)), 2)
                if stop < entry <= hard_max_entry:
                    shares, notional, max_risk = size_position(
                        entry=entry,
                        stop=stop,
                        risk_budget_usd=float(risk.get("opening_drive_max_trade_risk_usd", opening_drive_cfg.get("risk_budget_usd", risk.get("max_trade_risk_usd", 80)))),
                        notional_cap_usd=float(risk.get("opening_drive_notional_usd_max", opening_drive_cfg.get("notional_cap_usd", risk.get("initial_notional_usd_max", 50)))),
                    )
                    if notional >= float(risk.get("initial_notional_usd_min", 50)):
                        risk_per_share = max(entry - stop, 0.01)
                        return {
                            "ticker": symbol_row["symbol"],
                            "mode": "OPENING_DRIVE_LONG",
                            "trigger": "OPENING_DRIVE_LONG",
                            "strategy_family": "CatalystContinuationLong",
                            "catalyst_type": symbol_row.get("catalyst_type"),
                            "catalyst_summary": f"{symbol_row.get('catalyst_type')} | {', '.join(symbol_row.get('catalyst_notes') or [])}",
                            "thesis": symbol_row.get("why_tradeable") or "opening-drive continuation on a catalyst-backed name",
                            "entry": entry,
                            "stop": stop,
                            "target_1": round(entry + (risk_per_share * 1.5), 2),
                            "target_2": round(entry + (risk_per_share * 2.25), 2),
                            "shares": shares,
                            "notional_usd": notional,
                            "max_risk_usd": max_risk,
                            "spread_bps": spread_bps,
                            "max_slippage_bps": float(risk.get("opening_drive_max_slippage_bps", opening_drive_cfg.get("max_slippage_bps", 18))),
                            "why_tradeable": symbol_row.get("why_tradeable"),
                            "why_might_fail": symbol_row.get("why_might_fail") or "opening-drive failure, first-minute low loss, or immediate VWAP rejection",
                            "no_trade_if": list(symbol_row.get("hard_no_trade_conditions") or []) + [
                                "spread blows out",
                                "first-minute low fails",
                                "price loses opening-drive reference and cannot reclaim",
                            ],
                            "open_positions": open_positions,
                            "limit_price": round(entry, 2),
                            "hard_max_entry_price": hard_max_entry,
                            "time_in_force": "DAY",
                            "extended_hours": False,
                            "order_type": "LIMIT",
                            "time_stop": opening_drive_cfg.get("time_stop_et", "09:45:00"),
                            "force_flat_time": "15:45:00",
                            "opening_drive_reference_price": round(reference_price, 4),
                            "first_minute_volume": round(first_volume, 2),
                            "first_minute_dollar_volume": round(first_dollar_volume, 2),
                            "close_in_range_pct": round(close_quality, 4),
                            "research_conviction_score": int(symbol_row.get("research_conviction_score", 0)),
                            "attention_ignition_score": int(symbol_row.get("attention_ignition_score", 0)),
                            "pre_move_asymmetry_score": int(symbol_row.get("pre_move_asymmetry_score", 0)),
                            "execution_safety_score": int(symbol_row.get("execution_safety_score", 0)),
                            "live_validation_score": int(symbol_row.get("live_validation_score", 0)),
                            "opening_exit_manager_armed": True,
                            "data_sources": [f"{configured_market_data_provider(cfg)}_market_data", "alpaca_news", "sec_edgar", "benzinga", "reddit", "x_optional"],
                            "signal_context": {
                                "phase": phase,
                                "premarket_high": premarket_high,
                                "premarket_low": premarket_low,
                                "opening_drive_reference_price": reference_price,
                                "first_minute_high": first_high,
                                "first_minute_low": first_low,
                                "latest_vwap": latest_vwap,
                            },
                        }

    if len(regular_rows) < 6:
        return None

    vwap_values = _compute_vwap(regular_rows)
    closes = [(_bar_float(bar, "close", "c", "last") or 0.0) for _, bar in regular_rows]
    lows = [(_bar_float(bar, "low", "l") or close) for (_, bar), close in zip(regular_rows, closes)]
    highs = [(_bar_float(bar, "high", "h") or close) for (_, bar), close in zip(regular_rows, closes)]
    volumes = [(_bar_float(bar, "volume", "v", "vol") or 0.0) for _, bar in regular_rows]
    orb = _opening_range(regular_rows, bars_count=5)
    if not orb:
        return None

    continuation = evaluate_second_leg_continuation(
        symbol=symbol_row["symbol"],
        closes=closes,
        lows=lows,
        highs=highs,
        volumes=volumes,
        vwaps=vwap_values,
        spread_bps=spread_bps,
        premarket_high=premarket_high,
        opening_range_high=orb["high"],
        opening_range_low=orb["low"],
        max_spread_bps=float(risk.get("max_spread_bps", 60)),
        max_chase_pct=float(risk.get("continuation_max_chase_pct", 3.0)),
    )
    if continuation.get("action") != "BUY_NOW":
        return None
    mode = str(continuation.get("mode") or "SECOND_LEG_CONTINUATION_LONG")
    trigger = str(continuation.get("trigger") or mode)
    entry = float(continuation["entry"])
    stop = float(continuation["stop"])

    if entry <= stop:
        return None

    notional_cap = float(risk.get("initial_notional_usd_max", risk.get("initial_notional_min_usd", 50)))
    shares, notional, max_risk = size_position(
        entry=entry,
        stop=stop,
        risk_budget_usd=float(risk.get("max_trade_risk_usd", 80)),
        notional_cap_usd=notional_cap,
    )
    if notional < float(risk.get("initial_notional_usd_min", 50)):
        return None

    target_1 = round(entry + ((entry - stop) * 1.8), 2)
    target_2 = round(entry + ((entry - stop) * 2.6), 2)
    return {
        "ticker": symbol_row["symbol"],
        "mode": mode,
        "trigger": trigger,
        "strategy_family": "CatalystContinuationLong",
        "catalyst_type": symbol_row.get("catalyst_type"),
        "catalyst_summary": f"{symbol_row.get('catalyst_type')} | {', '.join(symbol_row.get('catalyst_notes') or [])}",
        "thesis": symbol_row.get("why_tradeable") or "catalyst-backed second-leg continuation setup",
        "entry": entry,
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "shares": shares,
        "notional_usd": notional,
        "max_risk_usd": max_risk,
        "spread_bps": spread_bps,
        "max_slippage_bps": float(risk.get("max_slippage_bps", 30)),
        "why_tradeable": symbol_row.get("why_tradeable"),
        "why_might_fail": symbol_row.get("why_might_fail") or "second-leg trigger fails, VWAP/base breaks, or volume expansion dries up",
        "no_trade_if": list(symbol_row.get("hard_no_trade_conditions") or []),
        "open_positions": open_positions,
        "limit_price": round(entry, 2),
        "hard_max_entry_price": round(entry * 1.0025, 2),
        "time_in_force": "DAY",
        "extended_hours": False,
        "order_type": "LIMIT",
        "research_conviction_score": int(symbol_row.get("research_conviction_score", 0)),
        "attention_ignition_score": int(symbol_row.get("attention_ignition_score", 0)),
        "pre_move_asymmetry_score": int(symbol_row.get("pre_move_asymmetry_score", 0)),
        "execution_safety_score": int(symbol_row.get("execution_safety_score", 0)),
        "live_validation_score": int(symbol_row.get("live_validation_score", 0)),
        "opening_exit_manager_armed": True,
        "data_sources": [f"{configured_market_data_provider(cfg)}_market_data", "alpaca_news", "sec_edgar", "benzinga", "reddit", "x_optional"],
        "signal_context": {"phase": phase, "lifecycle_state": lc.OPENING_CONTINUATION_ACTIVE, "secondary_lifecycle_state": lc.SECOND_LEG_CONTINUATION_ACTIVE, "premarket_high": premarket_high, "premarket_low": premarket_low, "opening_range_high": orb["high"], "opening_range_low": orb["low"], "second_leg_decision": continuation},
    }


def _mode_diagnostics(symbol_row: dict[str, Any], phase: str, quote: dict[str, Any], bars: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    risk = cfg.get("risk") or {}
    session = cfg.get("session") or cfg.get("schedule") or {}
    strategy = cfg.get("strategy") or {}
    opening_drive_cfg = strategy.get("opening_drive") or {}
    subminute_cfg = opening_drive_cfg.get("subminute") or {}
    last = _extract_quote_value(quote, "last", "price")
    spread_bps = float(symbol_row.get("spread_bps") or quote.get("spread_bps") or 0.0)
    quote_ts = _extract_quote_timestamp(quote)
    tz_name = session.get("timezone", "America/New_York")
    local_dt = quote_ts.astimezone(ZoneInfo(tz_name)) if quote_ts else None
    local_time = local_dt.time() if local_dt else time(0, 0)
    session_date = local_dt.date() if local_dt else None
    regular_rows = _session_rows(bars, tz_name, include_premarket=False, session_date=session_date)
    premarket_rows = _session_rows(bars, tz_name, include_premarket=True, session_date=session_date)
    premarket_highs = [(_bar_float(bar, "high", "h") or 0.0) for _, bar in premarket_rows]
    premarket_high = max(premarket_highs) if premarket_highs else float(symbol_row.get("premarket_high") or last or 0.0)

    attempted: list[dict[str, Any]] = []

    def record(mode: str, predicates: dict[str, bool], actuals: dict[str, Any], thresholds: dict[str, Any]) -> None:
        attempted.append(
            {
                "mode": mode,
                "passed_predicates": [key for key, value in predicates.items() if value],
                "failed_predicates": [key for key, value in predicates.items() if not value],
                "actuals": actuals,
                "thresholds": thresholds,
            }
        )

    if opening_drive_cfg.get("enabled", True) and subminute_cfg.get("enabled", True) and local_dt:
        in_window = _in_clock_window(local_time, opening_drive_cfg.get("entry_start_et", "09:30:00"), subminute_cfg.get("entry_cutoff_et", subminute_cfg.get("entry_end_et", "09:30:55")))
        samples = list((symbol_row.get("_opening_drive_tape") or {}).get("samples") or [])
        sample_prices = [float(sample.get("last") or 0.0) for sample in samples if float(sample.get("last") or 0.0) > 0]
        first_ts = _bar_timestamp({"timestamp": samples[0].get("timestamp")}) if samples else None
        last_ts = _bar_timestamp({"timestamp": samples[-1].get("timestamp")}) if samples else None
        elapsed = (last_ts - first_ts).total_seconds() if first_ts and last_ts else 0.0
        high_sample = max(sample_prices) if sample_prices else 0.0
        low_sample = min(sample_prices) if sample_prices else 0.0
        close_quality = _close_in_range_pct(float(last or 0.0), low_sample, high_sample) if high_sample else 0.0
        push_pct = (((float(last or 0.0) / sample_prices[0]) - 1.0) * 100.0) if sample_prices else 0.0
        break_bps = (((float(last or 0.0) / max(premarket_high, 0.01)) - 1.0) * 10000.0) if last else 0.0
        record(
            "SUBMINUTE_OPENING_DRIVE_LONG",
            {
                "in_subminute_window": in_window,
                "enough_quote_samples": len(samples) >= int(subminute_cfg.get("min_quote_samples", 3)),
                "enough_elapsed_seconds": elapsed >= float(subminute_cfg.get("min_elapsed_seconds", 10)),
                "close_in_range_ok": close_quality >= float(subminute_cfg.get("min_close_in_range_pct", 0.75)),
                "push_from_first_sample_ok": push_pct >= float(subminute_cfg.get("min_push_from_first_sample_pct", 0.15)),
                "break_above_reference_ok": break_bps >= float(subminute_cfg.get("min_break_above_reference_bps", 5.0)),
                "spread_ok": spread_bps <= float(risk.get("opening_drive_max_spread_bps", opening_drive_cfg.get("max_spread_bps", risk.get("max_spread_bps", 60)))),
            },
            {"samples": len(samples), "elapsed_seconds": round(elapsed, 3), "last": last, "premarket_high": premarket_high, "spread_bps": spread_bps, "close_in_range_pct": round(close_quality, 4), "push_from_first_sample_pct": round(push_pct, 4), "break_above_reference_bps": round(break_bps, 3)},
            {"min_quote_samples": int(subminute_cfg.get("min_quote_samples", 3)), "min_elapsed_seconds": float(subminute_cfg.get("min_elapsed_seconds", 10)), "min_close_in_range_pct": float(subminute_cfg.get("min_close_in_range_pct", 0.75)), "min_push_from_first_sample_pct": float(subminute_cfg.get("min_push_from_first_sample_pct", 0.15)), "min_break_above_reference_bps": float(subminute_cfg.get("min_break_above_reference_bps", 5.0))},
        )

    if opening_drive_cfg.get("enabled", True):
        in_window = _in_clock_window(local_time, opening_drive_cfg.get("entry_start_et", "09:30:00"), opening_drive_cfg.get("entry_cutoff_et", "09:34:59")) if local_dt else False
        first_bar = regular_rows[0][1] if regular_rows else {}
        first_close = _bar_float(first_bar, "close", "c", "last") or float(last or 0.0)
        first_high = _bar_float(first_bar, "high", "h") or first_close
        first_low = _bar_float(first_bar, "low", "l") or first_close
        first_volume = _bar_float(first_bar, "volume", "v", "vol") or 0.0
        first_dollar_volume = first_close * first_volume
        close_quality = _close_in_range_pct(first_close, first_low, first_high)
        max_spread = float(risk.get("opening_drive_max_spread_bps", opening_drive_cfg.get("max_spread_bps", risk.get("max_spread_bps", 60))))
        record(
            "OPENING_DRIVE_LONG",
            {
                "in_opening_drive_window": in_window,
                "enough_regular_bars": len(regular_rows) >= int(opening_drive_cfg.get("min_regular_bars", 1)),
                "first_minute_volume_ok": first_volume >= float(risk.get("opening_drive_min_first_minute_volume", opening_drive_cfg.get("min_first_minute_volume", 0))),
                "first_minute_dollar_volume_ok": first_dollar_volume >= float(risk.get("opening_drive_min_first_minute_dollar_volume", opening_drive_cfg.get("min_first_minute_dollar_volume", 0))),
                "close_in_range_ok": close_quality >= float(risk.get("opening_drive_min_close_in_range_pct", opening_drive_cfg.get("min_close_in_range_pct", 0.0))),
                "spread_ok": spread_bps <= max_spread,
                "above_reference_ok": bool(last is not None and float(last) >= premarket_high),
            },
            {"regular_bars": len(regular_rows), "first_volume": round(first_volume, 2), "first_dollar_volume": round(first_dollar_volume, 2), "close_in_range_pct": round(close_quality, 4), "last": last, "premarket_high": premarket_high, "spread_bps": spread_bps},
            {"min_regular_bars": int(opening_drive_cfg.get("min_regular_bars", 1)), "min_first_minute_volume": float(risk.get("opening_drive_min_first_minute_volume", opening_drive_cfg.get("min_first_minute_volume", 0))), "min_first_minute_dollar_volume": float(risk.get("opening_drive_min_first_minute_dollar_volume", opening_drive_cfg.get("min_first_minute_dollar_volume", 0))), "max_spread_bps": max_spread},
        )

    if len(regular_rows) >= 6:
        vwap_values = _compute_vwap(regular_rows)
        closes = [(_bar_float(bar, "close", "c", "last") or 0.0) for _, bar in regular_rows]
        lows = [(_bar_float(bar, "low", "l") or close) for (_, bar), close in zip(regular_rows, closes)]
        highs = [(_bar_float(bar, "high", "h") or close) for (_, bar), close in zip(regular_rows, closes)]
        volumes = [(_bar_float(bar, "volume", "v", "vol") or 0.0) for _, bar in regular_rows]
        orb = _opening_range(regular_rows, bars_count=5) or {}
        decision = evaluate_second_leg_continuation(
            symbol=str(symbol_row.get("symbol") or ""),
            closes=closes,
            lows=lows,
            highs=highs,
            volumes=volumes,
            vwaps=vwap_values,
            spread_bps=spread_bps,
            premarket_high=premarket_high,
            opening_range_high=orb.get("high"),
            opening_range_low=orb.get("low"),
            max_spread_bps=float(risk.get("max_spread_bps", 60)),
        )
        record(
            "SECOND_LEG_CONTINUATION_LONG",
            {key: key not in set(decision.get("failed_predicates") or []) for key in ["spread_ok", "volume_expansion_ok", "higher_low_ok", "fresh_trigger_ok", "chase_risk_ok"]},
            {**(decision.get("actuals") or {}), "regular_bars": len(regular_rows), "action": decision.get("action")},
            {"min_regular_bars": 6, "max_spread_bps": float(risk.get("max_spread_bps", 60))},
        )
    else:
        record(
            "SECOND_LEG_CONTINUATION_LONG",
            {"enough_regular_bars_for_fallback": False},
            {"regular_bars": len(regular_rows), "phase": phase},
            {"min_regular_bars": 6},
        )
    return {"attempted_modes": attempted}


def _classify_no_proposal(symbol_row: dict[str, Any], phase: str, quote: dict[str, Any], bars: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    diagnostics = _mode_diagnostics(symbol_row, phase, quote, bars, cfg)
    attempted = diagnostics.get("attempted_modes") or []
    failed: list[str] = []
    passed: list[str] = []
    for mode in attempted:
        failed.extend(str(item) for item in (mode.get("failed_predicates") or []))
        passed.extend(str(item) for item in (mode.get("passed_predicates") or []))
    hard_no_trade = {
        "spread_ok",
        "above_reference_ok",
        "close_in_range_ok",
        "first_minute_dollar_volume_ok",
        "first_minute_volume_ok",
    }
    if "in_subminute_window" in failed or "in_opening_drive_window" in failed:
        action = "WAIT"
        reason = "entry_mode_window_not_active"
    elif "enough_quote_samples" in failed or "enough_elapsed_seconds" in failed or "enough_regular_bars" in failed or "enough_regular_bars_for_fallback" in failed:
        action = "WAIT"
        reason = "needs_more_opening_tape"
    elif hard_no_trade.intersection(failed):
        action = "NO_TRADE"
        reason = "opening_tape_predicates_failed"
    else:
        action = "NO_TRADE"
        reason = "no_opening_mode_predicates_passed"
    return {
        "symbol": symbol_row.get("symbol"),
        "status": action,
        "action": action,
        "reason": reason,
        "phase": phase,
        "passed_predicates": sorted(set(passed)),
        "failed_predicates": sorted(set(failed)),
        **diagnostics,
    }


def run_live_monitor_once() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    repo_root = Path(__file__).resolve().parents[2]
    opening_drive_state_path = _opening_drive_state_path(repo_root)
    opening_drive_state = _load_opening_drive_state(opening_drive_state_path)
    cfg = load_live_config()
    no_order_brokerless_shadow = (
        os.getenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "false").strip().lower() not in {"1", "true", "yes", "on"}
        and os.getenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false").strip().lower() not in {"1", "true", "yes", "on"}
        and os.getenv("ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW", "false").strip().lower() in {"1", "true", "yes", "on"}
    )
    guards = active_guards(cfg)
    phase = session_phase(cfg)

    if not guards.get("live_armed"):
        return {"ok": True, "status": "disarm", "generated_at_utc": now, "reason": "live_armed_missing"}
    if guards["kill_switch"]:
        return {"ok": True, "status": "disarm", "generated_at_utc": now, "reason": "kill_switch_active"}
    if guards["disable_entries"]:
        return {"ok": True, "status": "disarm", "generated_at_utc": now, "reason": "disable_entries_active"}
    if should_force_flat(cfg):
        return {"ok": True, "status": "force_flat", "generated_at_utc": now, "reason": "force_flat_time_reached"}
    if phase != "ENTRY_WINDOW":
        return {"ok": True, "status": "watch", "generated_at_utc": now, "reason": f"phase={phase}"}

    watchlist = _load_active_watchlist(repo_root)
    if not watchlist:
        ticket = _load_authorized_trade_ticket(repo_root)
        reason = "no_valid_trade_authorization_ticket" if ticket is None or not validate_ticket(ticket).valid else "no_authorized_ticker_watchlist"
        return {"ok": True, "status": "disarm", "generated_at_utc": now, "reason": reason}
    active_ticket = _load_authorized_trade_ticket(repo_root)
    if active_ticket is not None and not validate_ticket(active_ticket).valid:
        active_ticket = None

    md = build_market_data_adapter(cfg)
    if no_order_brokerless_shadow:
        position_state = {"ok": True, "count": 0, "positions": [], "mode": "brokerless_no_order_shadow"}
    else:
        position_state = PositionManager(cfg=cfg).count_open_positions()
        if not position_state.get("ok"):
            return {"ok": True, "status": "disarm", "generated_at_utc": now, "reason": position_state.get("reason", "position_state_unavailable")}
    open_positions = int(position_state.get("count", 0))

    proposals = []
    details = []
    notifier = TelegramNotifier()
    router = None if no_order_brokerless_shadow else OrderRouter(cfg=cfg)
    submission_mode = "dry_run" if router is None else router.submission_mode()
    submission_armed = submission_mode in {"paper", "live"}
    live_armed = submission_mode == "live"
    max_positions = int((cfg.get("strategy") or {}).get("max_open_positions", 1))
    max_quote_age_ms = int((cfg.get("market_data") or {}).get("max_quote_age_ms_open", (cfg.get("risk") or {}).get("max_quote_age_ms", 1500)))

    for symbol_row in watchlist:
        symbol = symbol_row["symbol"]
        quote_res = md.get_quote(symbol)
        bars_res = md.get_bars_1m(symbol, limit=240)
        if not quote_res.get("ok") or not bars_res.get("ok"):
            details.append({"symbol": symbol, "status": "unhealthy", "quote_reason": quote_res.get("reason"), "bars_reason": bars_res.get("reason")})
            continue
        quote = quote_res.get("quote") or {}
        bars = bars_res.get("bars") or []
        quote_ts = _extract_quote_timestamp(quote)
        if quote_ts is None:
            details.append({"symbol": symbol, "status": "unhealthy", "reason": "missing_quote_timestamp"})
            continue
        quote_age_ms = int((datetime.now(timezone.utc) - quote_ts.astimezone(timezone.utc)).total_seconds() * 1000)
        if quote_age_ms > max_quote_age_ms:
            details.append({"symbol": symbol, "status": "unhealthy", "reason": "stale_quote", "quote_age_ms": quote_age_ms})
            continue
        quote_local_dt = quote_ts.astimezone(ZoneInfo((cfg.get("session") or {}).get("timezone", "America/New_York")))
        opening_drive_state, opening_drive_tape = _update_opening_drive_tape(opening_drive_state, symbol, quote, quote_local_dt)
        symbol_row_with_tape = {**symbol_row, "_opening_drive_tape": opening_drive_tape}
        candidate = _build_structured_candidate(symbol_row_with_tape, phase, quote, bars, cfg, open_positions=open_positions)
        if not candidate:
            details.append(_classify_no_proposal(symbol_row_with_tape, phase, quote, bars, cfg))
            continue
        proposal = build_trade_proposal(candidate)
        if active_ticket is not None and not ticket_authorizes_symbol(active_ticket, proposal.get("ticker")):
            reason = "ticket_does_not_authorize_symbol"
            append_audit_event("proposal_rejected", {"ticker": proposal.get("ticker"), "reason": reason, "proposal": proposal}, status="blocked")
            details.append({"symbol": symbol, "status": "blocked", "reason": reason})
            continue
        if active_ticket is not None:
            ticket_ok, ticket_reason = _validate_ticket_for_submission(proposal, active_ticket)
            if not ticket_ok:
                append_audit_event("proposal_rejected", {"ticker": proposal.get("ticker"), "reason": ticket_reason, "proposal": proposal}, status="blocked")
                details.append({"symbol": symbol, "status": "blocked", "reason": ticket_reason})
                continue
        ok, reason = validate_trade_plan(proposal, risk_config_for_validation(cfg))
        if not ok:
            append_audit_event("proposal_rejected", {"ticker": proposal["ticker"], "reason": reason, "proposal": proposal}, status="blocked")
            details.append({"symbol": symbol, "status": "blocked", "reason": reason})
            continue
        existing = find_recent_matching_proposal(proposal["ticker"], proposal["trigger"], cfg=cfg)
        if existing:
            details.append({"symbol": symbol, "status": "watch", "reason": "proposal_already_open", "plan_id": existing.get("plan_id")})
            continue
        save_proposal(proposal, cfg)
        append_audit_event("proposal_created", {"plan_id": proposal["plan_id"], "ticker": proposal["ticker"], "mode": proposal.get("mode"), "trigger": proposal["trigger"], "submission_mode": submission_mode})
        if notifier.configured():
            notifier.send(_proposal_alert_text(proposal))

        if submission_armed and router is not None:
            submit_result = router.submit_order(proposal)
            details.append({
                "symbol": symbol,
                "status": "submitted" if submit_result.get("ok") else "blocked",
                "reason": submit_result.get("reason"),
                "plan_id": proposal.get("plan_id"),
                "submission_mode": submit_result.get("mode"),
            })
            proposal["submission"] = submit_result
            proposals.append(proposal)
            if submit_result.get("ok"):
                _save_opening_drive_state(opening_drive_state_path, opening_drive_state)
                return {
                    "ok": True,
                    "status": "submitted_live" if submit_result.get("mode") == "live" else ("submitted_paper" if submit_result.get("mode") == "paper" else "previewed_dry_run"),
                    "generated_at_utc": now,
                    "phase": phase,
                    "live_order_submission_enabled": live_armed,
                    "paper_order_submission_enabled": submission_mode == "paper",
                    "broker_submission_mode": submission_mode,
                    "proposals": proposals,
                    "details": details,
                }
            continue

        proposals.append(proposal)
        if len(proposals) >= max_positions:
            break

    if proposals:
        _save_opening_drive_state(opening_drive_state_path, opening_drive_state)
        return {"ok": True, "status": "arm", "generated_at_utc": now, "phase": phase, "live_order_submission_enabled": live_armed, "paper_order_submission_enabled": submission_mode == "paper", "broker_submission_mode": submission_mode, "broker_state_mode": position_state.get("mode", "broker_checked"), "proposals": proposals, "details": details}
    if details and all(d.get("status") == "unhealthy" for d in details):
        _save_opening_drive_state(opening_drive_state_path, opening_drive_state)
        return {"ok": True, "status": "disarm", "generated_at_utc": now, "reason": "market_data_unhealthy", "details": details, "action": "DISABLE NEW ENTRIES"}
    _save_opening_drive_state(opening_drive_state_path, opening_drive_state)
    return {"ok": True, "status": "watch", "generated_at_utc": now, "phase": phase, "details": details}


if __name__ == "__main__":
    print(json.dumps(run_live_monitor_once()))
