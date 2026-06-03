#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.research import lifecycle as lc
from src.strategy.second_leg_continuation import evaluate_second_leg_continuation


ET = ZoneInfo("America/New_York")


def _ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(ET)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(ET)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _aggregate_trade_bars(raw_trades: Path, symbol: str, start_et: datetime, end_et: datetime) -> list[dict[str, Any]]:
    bars: dict[datetime, dict[str, Any]] = {}
    for row in _read_jsonl(raw_trades):
        if str(row.get("symbol") or "").upper() != symbol:
            continue
        try:
            ts = _ts(row.get("timestamp"))
            price = float(row.get("price"))
            size = float(row.get("size") or 0.0)
        except Exception:
            continue
        if ts < start_et or ts > end_et:
            continue
        bucket = ts.replace(second=0, microsecond=0)
        bar = bars.setdefault(bucket, {"timestamp_et": bucket.isoformat(), "open": price, "high": price, "low": price, "close": price, "volume": 0.0, "dollar_volume": 0.0, "trade_count": 0})
        bar["high"] = max(float(bar["high"]), price)
        bar["low"] = min(float(bar["low"]), price)
        bar["close"] = price
        bar["volume"] = float(bar["volume"]) + size
        bar["dollar_volume"] = float(bar["dollar_volume"]) + (price * size)
        bar["trade_count"] = int(bar["trade_count"]) + 1
    out = [bars[key] for key in sorted(bars)]
    for bar in out:
        vol = float(bar["volume"])
        bar["vwap"] = round(float(bar["dollar_volume"]) / vol, 6) if vol else float(bar["close"])
    return out


def _quote_spreads(raw_quotes: Path, symbol: str, start_et: datetime, end_et: datetime) -> dict[str, float]:
    spreads: dict[str, list[float]] = {}
    for row in _read_jsonl(raw_quotes):
        if str(row.get("symbol") or "").upper() != symbol:
            continue
        try:
            ts = _ts(row.get("timestamp"))
            bid = float(row.get("bid"))
            ask = float(row.get("ask"))
        except Exception:
            continue
        if ts < start_et or ts > end_et or bid <= 0 or ask <= 0 or ask < bid:
            continue
        mid = (bid + ask) / 2.0
        bucket = ts.replace(second=0, microsecond=0).isoformat()
        spreads.setdefault(bucket, []).append(((ask - bid) / mid) * 10000.0)
    return {bucket: sum(values) / len(values) for bucket, values in spreads.items() if values}


def replay_continuation(input_dir: Path, output_dir: Path, symbol: str = "INFQ", window_start: str = "2026-05-22T09:35:00-04:00", window_end: str = "2026-05-22T09:50:00-04:00") -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    start_et = _ts(window_start)
    end_et = _ts(window_end)
    regular_start = start_et.replace(hour=9, minute=30, second=0, microsecond=0)
    bars = _aggregate_trade_bars(input_dir / "raw_trades.jsonl", symbol, regular_start, end_et)
    spreads = _quote_spreads(input_dir / "raw_quotes.jsonl", symbol, regular_start, end_et)

    decisions_path = output_dir / "decisions.jsonl"
    proposals_path = output_dir / "proposals.jsonl"
    decisions_path.write_text("")
    proposals_path.write_text("")
    opening_bars = [bar for bar in bars if regular_start <= _ts(bar["timestamp_et"]) <= end_et]
    opening_range = opening_bars[:5]
    opening_range_high = max((float(bar["high"]) for bar in opening_range), default=None)
    opening_range_low = min((float(bar["low"]) for bar in opening_range), default=None)
    premarket_high = opening_range_high
    decisions: list[dict[str, Any]] = []
    lifecycle_transitions: list[dict[str, Any]] = []
    last_state: str | None = None
    proposal_count = 0

    for idx, bar in enumerate(opening_bars, start=1):
        ts = _ts(bar["timestamp_et"])
        if ts < start_et:
            continue
        history = opening_bars[:idx]
        closes = [float(item["close"]) for item in history]
        lows = [float(item["low"]) for item in history]
        highs = [float(item["high"]) for item in history]
        volumes = [float(item["volume"]) for item in history]
        vwaps = [float(item.get("vwap") or item["close"]) for item in history]
        spread = spreads.get(ts.replace(second=0, microsecond=0).isoformat(), 30.0)
        decision = evaluate_second_leg_continuation(
            symbol=symbol,
            closes=closes,
            lows=lows,
            highs=highs,
            volumes=volumes,
            vwaps=vwaps,
            spread_bps=spread,
            premarket_high=premarket_high,
            opening_range_high=opening_range_high,
            opening_range_low=opening_range_low,
            max_spread_bps=80.0,
            max_chase_pct=3.0,
        )
        row = {"symbol": symbol, "timestamp_et": ts.isoformat(), "decision": decision, "bar": bar, "mode": decision.get("mode")}
        decisions.append(row)
        with decisions_path.open("a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        state = str(decision.get("lifecycle_state") or lc.SECOND_LEG_RESET)
        if state != last_state:
            lifecycle_transitions.append({"timestamp_et": ts.isoformat(), "state": state, "action": decision.get("action"), "mode": decision.get("mode")})
            last_state = state
        if decision.get("action") == "BUY_NOW":
            proposal_count += 1
            proposal = {
                "symbol": symbol,
                "timestamp_et": ts.isoformat(),
                "mode": decision.get("mode"),
                "trigger": decision.get("trigger"),
                "entry": decision.get("entry"),
                "stop": decision.get("stop"),
                "hypothetical": True,
                "orders_submitted": False,
            }
            with proposals_path.open("a") as fh:
                fh.write(json.dumps(proposal, sort_keys=True) + "\n")

    action_rank = {"BUY_NOW": 3, "WAIT": 2, "SWITCH_TO_BACKUP": 1, "NO_TRADE_EXTENDED": 0, "CANCEL_PRIMARY": 0}
    best = max(decisions, key=lambda row: action_rank.get(str((row.get("decision") or {}).get("action")), -1)) if decisions else None
    failed = Counter()
    for row in decisions:
        failed.update(str(item) for item in (row.get("decision") or {}).get("failed_predicates") or [])
    summary = {
        "ok": True,
        "input_artifact_path": str(input_dir),
        "replay_window_start_et": start_et.isoformat(),
        "replay_window_end_et": end_et.isoformat(),
        "research_leader": symbol,
        "executable_primary": None,
        "lifecycle_transitions": lifecycle_transitions,
        "first_decision": decisions[0] if decisions else None,
        "best_decision": best,
        "last_decision": decisions[-1] if decisions else None,
        "proposal_count": proposal_count,
        "hypothetical_order_count": proposal_count,
        "orders_submitted": False,
        "top_failed_predicates": [{"predicate": key, "count": count} for key, count in failed.most_common(10)],
        "whether_0946_style_move_was_caught": proposal_count > 0,
        "caught_0946_style_move": proposal_count > 0,
        "mode_coverage": sorted({str((row.get("decision") or {}).get("mode")) for row in decisions if (row.get("decision") or {}).get("mode")}),
        "windows_monitored": ["09:35-09:50_ET_continuation"],
        "continuation_handoff_started": True,
        "continuation_monitor_started": True,
        "stream_source_counts": {
            "raw_quote_count": sum(1 for row in _read_jsonl(input_dir / "raw_quotes.jsonl") if str(row.get("symbol") or "").upper() == symbol),
            "raw_trade_count": sum(1 for row in _read_jsonl(input_dir / "raw_trades.jsonl") if str(row.get("symbol") or "").upper() == symbol),
            "minute_bars_built": len(opening_bars),
            "decisions_count": len(decisions),
        },
        "decisions_path": str(decisions_path),
        "proposals_path": str(proposals_path),
    }
    (output_dir / "final_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay captured INFQ 09:35-09:50 ET continuation tape without orders.")
    parser.add_argument("--input-dir", default="reports/live_monitor/runs/opening_stream_2026-05-22_132548")
    parser.add_argument("--output-dir", default="reports/live_monitor/runs/replay_infq_2026-05-22_continuation")
    parser.add_argument("--symbol", default="INFQ")
    args = parser.parse_args()
    summary = replay_continuation(Path(args.input_dir), Path(args.output_dir), symbol=args.symbol.upper())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
