from __future__ import annotations

import argparse
import json
import os
import threading
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

import yaml

from ..adapters.alpaca_streams import AlpacaStreamsAdapter
from ..common.config import load_live_config, repo_root
from ..execution.order_router import OrderRouter
from ..features.opening_tape import OpeningTapeTracker
from ..execution.proposal_builder import build_trade_proposal
from ..research import lifecycle as lc
from ..research.trade_authorization_ticket import load_today_ticket, validate_submission_against_ticket, validate_ticket
from ..strategy.opening_burst_hyper_long import evaluate_opening_burst_signal


def _ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _close_in_range_pct(features: dict[str, Any]) -> float:
    high = float(features.get("high_60s") or features.get("high_30s") or features.get("latest_price") or 0.0)
    low = float(features.get("low_60s") or features.get("low_30s") or features.get("latest_price") or 0.0)
    close = float(features.get("close_60s") or features.get("close_30s") or features.get("latest_price") or 0.0)
    if high <= low:
        return 1.0 if close >= low and close > 0 else 0.0
    return max(0.0, min(1.0, (close - low) / (high - low)))


def load_stream_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    events.sort(key=lambda row: str(row.get("timestamp") or row.get("ts") or ""))
    return events


def replay_opening_stream(
    candidate: dict[str, Any],
    events: list[dict[str, Any]],
    cfg: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    symbol = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
    if not symbol:
        return {"ok": False, "status": "NO_TRADE", "reason": "missing_candidate_symbol"}
    if not events:
        return {"ok": True, "status": "NO_TRADE", "reason": "STREAM_REQUIRED_FOR_OPENING_ENTRY", "decisions": []}

    output_dir = output_dir or Path("reports/live_monitor/runs/replay")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_quotes = output_dir / "raw_quotes.jsonl"
    raw_trades = output_dir / "raw_trades.jsonl"
    features_path = output_dir / "opening_tape_features.jsonl"
    decisions_path = output_dir / "decisions.jsonl"
    orders_path = output_dir / "orders.jsonl"
    for path in [raw_quotes, raw_trades, features_path, decisions_path, orders_path]:
        path.write_text("")

    tracker = OpeningTapeTracker(
        symbol,
        premarket_high=candidate.get("premarket_high"),
        premarket_vwap=candidate.get("premarket_vwap"),
        thesis_break=candidate.get("thesis_break"),
        expected_opening_dollar_volume_60s=candidate.get("expected_opening_dollar_volume_60s"),
        premarket_dollar_volume_per_minute=candidate.get("premarket_dollar_volume_per_minute"),
    )
    decisions: list[dict[str, Any]] = []
    last_decision: dict[str, Any] | None = None
    for event in events:
        event_symbol = str(event.get("symbol") or symbol).upper()
        if event_symbol != symbol:
            continue
        event_type = str(event.get("type") or event.get("event_type") or "").lower()
        ts = _ts(event.get("timestamp") or event.get("ts"))
        if event_type == "quote":
            tracker.update_quote(event)
            with raw_quotes.open("a") as fh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
        elif event_type == "trade":
            tracker.update_trade(event)
            with raw_trades.open("a") as fh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
        else:
            continue
        features = tracker.features(ts)
        with features_path.open("a") as fh:
            fh.write(json.dumps(features, sort_keys=True) + "\n")
        decision = evaluate_opening_burst_signal(candidate, features, cfg, now=ts)
        decisions.append(decision)
        last_decision = decision
        with decisions_path.open("a") as fh:
            fh.write(json.dumps({"symbol": symbol, "decision": decision, "features": features}, sort_keys=True) + "\n")
        if decision.get("action") == "BUY_NOW":
            with orders_path.open("a") as fh:
                fh.write(json.dumps({"candidate": candidate, "decision": decision}, sort_keys=True) + "\n")
            break

    status = "BUY_NOW" if last_decision and last_decision.get("action") == "BUY_NOW" else (last_decision or {}).get("action", "NO_TRADE")
    per_symbol_summary = _decision_summary(decisions_path, [symbol])
    raw_quote_count = _line_count(raw_quotes)
    raw_trade_count = _line_count(raw_trades)
    decision_count = _line_count(decisions_path)
    summary = {
        "ok": True,
        "status": status,
        "symbol": symbol,
        "decisions": decisions,
        "final_decision": last_decision,
        "output_dir": str(output_dir),
        "raw_quotes": str(raw_quotes),
        "raw_trades": str(raw_trades),
        "features": str(features_path),
        "decision_log": str(decisions_path),
        "decisions_path": str(decisions_path),
        "orders": str(orders_path),
        "raw_quote_count": raw_quote_count,
        "raw_trade_count": raw_trade_count,
        "decision_count": decision_count,
        "decisions_count": decision_count,
        "proposal_count": 1 if status == "BUY_NOW" else 0,
        "orders_submitted": False,
        "stream_capture_started": bool(events),
        "stream_capture_completed": raw_quote_count > 0 and raw_trade_count > 0 and decision_count > 0,
        "per_symbol_decision_summary": per_symbol_summary,
        "mode_coverage": {
            "opening_burst_ran": decision_count > 0,
            "continuation_monitor_started": status != "BUY_NOW",
            "second_leg_monitor_started": status != "BUY_NOW",
            "windows_monitored": sorted({str(item.get("window") or "unknown") for item in decisions}),
        },
    }
    (output_dir / "final_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _load_opening_cfg() -> dict[str, Any]:
    path = repo_root() / "config" / "opening_bell.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(errors="replace").splitlines() if line.strip())


def _decision_summary(decisions_path: Path, symbols: list[str]) -> dict[str, Any]:
    rows_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
    if decisions_path.exists():
        for line in decisions_path.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            symbol = str(row.get("symbol") or ((row.get("decision") or {}).get("symbol")) or "").upper()
            if symbol in rows_by_symbol:
                rows_by_symbol[symbol].append(row)
    summary: dict[str, Any] = {}
    for symbol, rows in rows_by_symbol.items():
        actions: dict[str, int] = {}
        failed: dict[str, int] = {}
        passed: dict[str, int] = {}
        max_scores: dict[str, float] = {}
        best_row: dict[str, Any] | None = None
        windows: set[str] = set()
        for row in rows:
            decision = row.get("decision") or row
            action = str(decision.get("action") or "UNKNOWN")
            actions[action] = actions.get(action, 0) + 1
            if decision.get("window"):
                windows.add(str(decision.get("window")))
            for key in decision.get("failed_predicates") or []:
                failed[str(key)] = failed.get(str(key), 0) + 1
            for key in decision.get("passed_predicates") or []:
                passed[str(key)] = passed.get(str(key), 0) + 1
            actuals = decision.get("actuals") or {}
            for key in ["opening_drive_score", "volume_burst_score", "hyper_trade_score", "opening_strategy_score", "infq_archetype_score"]:
                try:
                    value = float(actuals.get(key))
                except Exception:
                    continue
                max_scores[key] = max(value, max_scores.get(key, 0.0))
            if best_row is None or (decision.get("action") == "BUY_NOW") or float((decision.get("actuals") or {}).get("opening_drive_score") or 0.0) > float(((best_row.get("decision") or best_row).get("actuals") or {}).get("opening_drive_score") or 0.0):
                best_row = row
        top_failed = sorted(failed.items(), key=lambda item: item[1], reverse=True)[:8]
        lifecycle_state = lc.OPENING_DRIVE_ACTIVE if actions.get("BUY_NOW") else (lc.SECOND_LEG_WATCH if any(key in failed for key in ["opening_drive_score_ok", "volume_burst_ok", "inside_opening_burst_window"]) else lc.PREMARKET_BUILDING)
        if failed.get("opening_burst_window_closed") or failed.get("continuation_handoff_required"):
            lifecycle_state = lc.SECOND_LEG_WATCH
        best_action = "BUY_NOW" if actions.get("BUY_NOW") else ("WAIT_FOR_SECOND_LEG" if lifecycle_state == lc.SECOND_LEG_WATCH else lc.NO_TRADE_EXTENDED)
        summary[symbol] = {
            "decision_count": len(rows),
            "decisions_count": len(rows),
            "proposal_count": 0,
            "best_action": best_action,
            "best_window": ((best_row or {}).get("decision") or best_row or {}).get("window"),
            "max_scores": max_scores,
            "top_failed_predicates": [{"predicate": key, "count": count} for key, count in top_failed],
            "top_passed_predicates": [{"predicate": key, "count": count} for key, count in sorted(passed.items(), key=lambda item: item[1], reverse=True)[:8]],
            "lifecycle_state": lifecycle_state,
            "next_action": best_action,
            "action_counts": actions,
            "first_decision": (rows[0].get("decision") or rows[0]) if rows else None,
            "best_decision": (best_row.get("decision") or best_row) if best_row else None,
            "last_decision": (rows[-1].get("decision") or rows[-1]) if rows else None,
            "mode_coverage": sorted(windows),
            "windows_monitored": sorted(windows),
            "discarded_or_kept": "kept_as_second_leg_watch" if lifecycle_state == lc.SECOND_LEG_WATCH else ("discarded_no_trade_extended" if lifecycle_state in {lc.NO_TRADE_EXTENDED, lc.EXHAUSTED_OR_DISTRIBUTING} else "active"),
        }
    return summary


def _last_decision_at(decisions_path: Path) -> str | None:
    if not decisions_path.exists():
        return None
    last: str | None = None
    for line in decisions_path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        features = row.get("features") or {}
        last = features.get("latest_trade_timestamp") or features.get("latest_quote_timestamp") or last
    return last


def _premarket_minutes_elapsed(packet: dict[str, Any] | None = None) -> float:
    observed = ((packet or {}).get("market_snapshot") or {}).get("observed_at")
    if not observed:
        return 330.0
    try:
        observed_at = _ts(observed)
    except Exception:
        return 330.0
    local = observed_at.astimezone(timezone.utc)
    premarket_start = datetime.combine(local.date(), time(hour=8, minute=0), tzinfo=timezone.utc)
    regular_open = datetime.combine(local.date(), time(hour=13, minute=30), tzinfo=timezone.utc)
    if local <= premarket_start:
        return 1.0
    end = min(local, regular_open)
    return max(1.0, (end - premarket_start).total_seconds() / 60.0)


def _opening_candidate_from_report_row(row: dict[str, Any], packet: dict[str, Any] | None = None) -> dict[str, Any]:
    symbol = str(row.get("symbol") or row.get("ticker") or "").upper()
    packet = packet or {}
    packet_scorecard = packet.get("scorecard") or {}
    infq_archetype = packet.get("infq_archetype") or {}
    infq_score = _float_or_none(infq_archetype.get("infq_archetype_score"))
    hyper = _float_or_none(row.get("hyper_trade_score")) or _float_or_none(packet_scorecard.get("hyper_trade_score")) or 0.0
    lane_tags = sorted(set((row.get("lane_tags") or []) + (packet_scorecard.get("lane_tags") or []) + (infq_archetype.get("tags") or [])))
    opening_score = max(float(hyper), float(infq_score or 0.0))
    premarket_total = _float_or_none(row.get("premarket_dollar_volume")) or _float_or_none(((packet.get("market_snapshot") or {}).get("premarket_dollar_volume")))
    expected_60s = None
    if premarket_total:
        expected_60s = premarket_total / _premarket_minutes_elapsed(packet)
    return {
        "ticker": symbol,
        "symbol": symbol,
        "hyper_trade_score": hyper,
        "opening_strategy_score": opening_score,
        "infq_archetype_score": infq_score,
        "lane_tags": lane_tags or ["VERIFIED_CATALYST_RUNNER"],
        "entry_cap": row.get("entry_cap") or row.get("hard_max_entry_price") or row.get("last_price"),
        "premarket_high": row.get("premarket_high") or row.get("last_price"),
        "premarket_dollar_volume": premarket_total,
        "expected_opening_dollar_volume_60s": expected_60s,
        "premarket_dollar_volume_per_minute": expected_60s,
    }


def _load_morning_candidates(limit: int = 3) -> list[dict[str, Any]]:
    trade_date = datetime.now().strftime("%Y-%m-%d")
    ticket = load_today_ticket(repo_root(), trade_date)
    ticket_validation = validate_ticket(ticket)
    if not ticket_validation.valid:
        return []
    ticker = str((ticket or {}).get("authorized_ticker") or "").upper()
    return [
        {
            "ticker": ticker,
            "symbol": ticker,
            "authorized_strategy": ticket.get("authorized_strategy") or ticket.get("strategy"),
            "trade_authorization_ticket": ticket,
        }
    ]


def run_live_opening_stream_supervisor(
    candidates: list[dict[str, Any]],
    *,
    output_dir: Path,
    cfg: dict[str, Any] | None = None,
    max_seconds: float | None = None,
) -> dict[str, Any]:
    cfg = cfg or _load_opening_cfg()
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = sorted({str(candidate.get("ticker") or candidate.get("symbol") or "").upper() for candidate in candidates if candidate.get("ticker") or candidate.get("symbol")})
    if not symbols:
        return {"ok": False, "reason": "no_stream_symbols"}
    trackers: dict[str, OpeningTapeTracker] = {}
    candidate_by_symbol = {str(candidate.get("ticker") or candidate.get("symbol")).upper(): candidate for candidate in candidates}
    fired_symbols: set[str] = set()
    blocked_proposals: list[dict[str, Any]] = []
    emitted_proposals: list[dict[str, Any]] = []
    order_results: list[dict[str, Any]] = []
    decisions_path = output_dir / "decisions.jsonl"
    proposals_path = output_dir / "proposals.jsonl"
    order_results_path = output_dir / "order_results.jsonl"
    summary_path = output_dir / "final_summary.json"
    for path in [decisions_path, proposals_path, order_results_path, summary_path]:
        path.write_text("")
    live_orders_allowed = os.getenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
    order_router = OrderRouter(cfg=load_live_config()) if live_orders_allowed else None

    def tracker_for(symbol: str) -> OpeningTapeTracker:
        if symbol not in trackers:
            candidate = candidate_by_symbol[symbol]
            trackers[symbol] = OpeningTapeTracker(
                symbol,
                premarket_high=candidate.get("premarket_high"),
                premarket_vwap=candidate.get("premarket_vwap"),
                thesis_break=candidate.get("thesis_break"),
                expected_opening_dollar_volume_60s=candidate.get("expected_opening_dollar_volume_60s"),
                premarket_dollar_volume_per_minute=candidate.get("premarket_dollar_volume_per_minute"),
            )
        return trackers[symbol]

    def maybe_decide(symbol: str, ts: datetime) -> None:
        if symbol in fired_symbols:
            return
        candidate = candidate_by_symbol[symbol]
        features = tracker_for(symbol).features(ts)
        decision = evaluate_opening_burst_signal(candidate, features, cfg, now=ts)
        with decisions_path.open("a") as fh:
            fh.write(json.dumps({"symbol": symbol, "decision": decision, "features": features}, sort_keys=True, default=str) + "\n")
        if decision.get("action") != "BUY_NOW":
            return
        fired_symbols.add(symbol)
        entry = float(decision["entry"])
        stop = float(candidate.get("thesis_break") or max(entry * 0.97, entry - 0.25))
        if stop >= entry:
            blocked = {"symbol": symbol, "status": "blocked", "reason": "invalid_stop_not_below_entry", "entry": entry, "stop": stop}
            blocked_proposals.append(blocked)
            with proposals_path.open("a") as fh:
                fh.write(json.dumps(blocked, sort_keys=True, default=str) + "\n")
            return
        risk_per_share = entry - stop
        shares = max(1, int(float(decision.get("notional_usd") or 100) / max(entry, 0.01)))
        proposal = build_trade_proposal(
            {
                **candidate,
                "ticker": symbol,
                "trigger": "OPENING_BURST_HYPER_LONG",
                "mode": "OPENING_BURST_HYPER_LONG",
                "strategy_family": "CatalystContinuationLong",
                "entry": entry,
                "stop": stop,
                "target_1": float(candidate.get("target_1") or entry + (risk_per_share * 1.8)),
                "target_2": float(candidate.get("target_2") or entry + (risk_per_share * 2.6)),
                "shares": shares,
                "notional_usd": decision.get("notional_usd") or 100,
                "max_risk_usd": round(risk_per_share * shares, 2),
                "first_minute_volume": features.get("window_volume_60s"),
                "first_minute_dollar_volume": features.get("window_dollar_volume_60s") or features.get("absolute_dollar_volume_60s"),
                "close_in_range_pct": features.get("close_in_range_pct") or round(_close_in_range_pct(features), 4),
                "spread_bps": features.get("spread_bps"),
                "max_slippage_bps": ((cfg.get("opening_bell") or {}).get("order") or {}).get("slippage_cap_bps", 20),
                "opening_drive_reference_price": features.get("regular_open_price") or features.get("first_trade_price") or candidate.get("premarket_high") or entry,
                "limit_price": decision.get("limit_price"),
                "hard_max_entry_price": decision.get("entry_cap"),
                "opening_exit_manager_armed": True,
            }
        )
        if order_router is not None:
            ticket = candidate.get("trade_authorization_ticket") or load_today_ticket(repo_root())
            ticket_ok, ticket_reason = validate_submission_against_ticket(proposal, ticket)
            if not ticket_ok:
                blocked = {"symbol": symbol, "status": "blocked", "reason": ticket_reason, "proposal": proposal}
                blocked_proposals.append(blocked)
                with proposals_path.open("a") as fh:
                    fh.write(json.dumps(blocked, sort_keys=True, default=str) + "\n")
                return
        emitted_proposals.append(proposal)
        with proposals_path.open("a") as fh:
            fh.write(json.dumps(proposal, sort_keys=True, default=str) + "\n")
        if order_router is not None:
            result = order_router.submit_order(proposal)
            order_results.append({"symbol": symbol, "proposal": proposal, "result": result})
            with order_results_path.open("a") as fh:
                fh.write(json.dumps(order_results[-1], sort_keys=True, default=str) + "\n")
            if result.get("ok") and result.get("mode") == "live":
                adapter.stop()

    def on_quote(payload: dict[str, Any]) -> None:
        symbol = str(payload.get("symbol") or "").upper()
        if symbol not in candidate_by_symbol:
            return
        tracker_for(symbol).update_quote(payload)
        maybe_decide(symbol, _ts(payload.get("timestamp")))

    def on_trade(payload: dict[str, Any]) -> None:
        symbol = str(payload.get("symbol") or "").upper()
        if symbol not in candidate_by_symbol:
            return
        tracker_for(symbol).update_trade(payload)
        maybe_decide(symbol, _ts(payload.get("timestamp")))

    adapter = AlpacaStreamsAdapter(output_dir=output_dir, feed=((load_live_config().get("market_data") or {}).get("feed") or None))
    adapter.subscribe_quotes_and_trades(symbols, quote_handler=on_quote, trade_handler=on_trade)
    if max_seconds is None:
        raw_max_seconds = os.getenv("ROI_SNIPS_OPENING_STREAM_MAX_SECONDS", "900")
        try:
            max_seconds = float(raw_max_seconds)
        except Exception as exc:
            raise ValueError("invalid_opening_stream_max_seconds") from exc
    if max_seconds <= 0:
        raise ValueError("invalid_opening_stream_max_seconds")
    stopped_by_timer = False

    def stop_after_timeout() -> None:
        nonlocal stopped_by_timer
        stopped_by_timer = True
        adapter.stop()

    timer = threading.Timer(max_seconds, stop_after_timeout)
    timer.daemon = True
    start_payload = {
        "ok": True,
        "mode": "live_order_submission" if live_orders_allowed else "shadow_no_order_submission",
        "symbols": symbols,
        "output_dir": str(output_dir),
        "max_seconds": max_seconds,
        "orders_allowed": live_orders_allowed,
        "orders_submitted": False,
        "stream_capture_started": True,
        "raw_quotes": str(output_dir / "raw_quotes.jsonl"),
        "raw_trades": str(output_dir / "raw_trades.jsonl"),
        "decisions": str(decisions_path),
        "proposals": str(proposals_path),
        "order_results": str(order_results_path),
        "fast_cancel_ready": True,
        "opening_exit_manager_ready": True,
        "stream_capture_started_at": datetime.now(timezone.utc).isoformat(),
        "continuation_monitor_start_et": "09:35:00",
    }
    (output_dir / "supervisor_start.json").write_text(json.dumps(start_payload, indent=2, sort_keys=True))
    try:
        timer.start()
        adapter.run()
        ok = True
        reason = None
    except Exception as exc:
        ok = False
        reason = str(exc)
    finally:
        timer.cancel()
    per_symbol_summary = _decision_summary(decisions_path, symbols)
    for proposal in emitted_proposals:
        symbol = str(proposal.get("ticker") or "").upper()
        if symbol in per_symbol_summary:
            per_symbol_summary[symbol]["proposal_count"] = per_symbol_summary[symbol].get("proposal_count", 0) + 1
    raw_quote_count = _line_count(output_dir / "raw_quotes.jsonl")
    raw_trade_count = _line_count(output_dir / "raw_trades.jsonl")
    decision_count = _line_count(decisions_path)
    stream_captured = raw_quote_count > 0 and raw_trade_count > 0 and decision_count > 0
    continuation_requested = os.getenv("ROI_SNIPS_RUN_CONTINUATION_MONITOR", "").strip().lower() in {"1", "true", "yes", "on"}
    continuation_started = bool(live_orders_allowed or continuation_requested)
    zero_reason = None
    if not emitted_proposals:
        parts = []
        for symbol, row in per_symbol_summary.items():
            failed = ", ".join(item["predicate"] for item in row.get("top_failed_predicates", [])[:3]) or "no_predicate_rows"
            parts.append(f"{symbol}: {row.get('best_action')} because {failed}")
        zero_reason = "; ".join(parts) if parts else "no_decisions_recorded"
    validation_status = "OK" if ok and stream_captured else ("INTERNAL_FAILURE" if not ok else "SHADOW_INVALID")
    summary = {
        **start_payload,
        "ok": ok,
        "status": validation_status,
        "reason": reason,
        "broker_account_inspected": False,
        "broker_orders_inspected": False,
        "broker_positions_inspected": False,
        "stream_capture_heartbeat_at": datetime.now(timezone.utc).isoformat(),
        "continuation_monitor_started_at": datetime.now(timezone.utc).isoformat() if continuation_started else None,
        "continuation_monitor_heartbeat_at": datetime.now(timezone.utc).isoformat() if continuation_started else None,
        "last_decision_at": _last_decision_at(decisions_path),
        "candidate_state_by_symbol": per_symbol_summary,
        "stopped_by_timer": stopped_by_timer,
        "stream_captured": stream_captured,
        "stream_capture_completed": stream_captured,
        "raw_quote_count": raw_quote_count,
        "raw_trade_count": raw_trade_count,
        "decision_count": decision_count,
        "decisions_count": decision_count,
        "proposal_count": len(emitted_proposals),
        "blocked_proposal_count": len(blocked_proposals),
        "fired_symbols": sorted(fired_symbols),
        "blocked_proposals": blocked_proposals,
        "order_result_count": len(order_results),
        "order_results_tail": order_results[-3:],
        "orders_submitted": any((item.get("result") or {}).get("ok") and (item.get("result") or {}).get("mode") == "live" for item in order_results),
        "stream_status": adapter.snapshot() if hasattr(adapter, "snapshot") else {},
        "per_symbol_decision_summary": per_symbol_summary,
        "mode_coverage": {
            "opening_burst_ran": decision_count > 0,
            "continuation_monitor_started": continuation_started,
            "orb_vwap_monitor_started": continuation_started,
            "second_leg_monitor_started": continuation_started,
            "stream_captured": stream_captured,
            "handoff_completed": continuation_started,
        },
        "zero_proposal_reason": zero_reason,
        "no_proposal_root_cause": zero_reason,
        "windows_monitored": sorted({window for row in per_symbol_summary.values() for window in (row.get("windows_monitored") or [])}),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay opening stream events through deterministic opening-burst supervisor")
    parser.add_argument("--candidate-json")
    parser.add_argument("--events-jsonl")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--candidates-from-morning", action="store_true")
    parser.add_argument("--max-seconds", type=float)
    args = parser.parse_args()
    if args.live:
        candidates = _load_morning_candidates() if args.candidates_from_morning else [json.loads(Path(args.candidate_json).read_text())]
        print(json.dumps(run_live_opening_stream_supervisor(candidates, output_dir=Path(args.output_dir), max_seconds=args.max_seconds), default=str))
        return
    if not args.candidate_json or not args.events_jsonl:
        raise SystemExit("--candidate-json and --events-jsonl are required unless --live is set")
    candidate = json.loads(Path(args.candidate_json).read_text())
    cfg = {
        "opening_bell": {
            "data": {"max_quote_age_ms": 1000},
            "thresholds": {
                "first_10s": {"min_hyper_trade_score": 8.0, "min_opening_drive_score": 8.0, "min_volume_burst_score": 7.0},
                "first_30s": {"min_hyper_trade_score": 7.5, "min_opening_drive_score": 7.5, "min_volume_burst_score": 6.5},
                "first_60s": {"min_hyper_trade_score": 7.0, "min_opening_drive_score": 7.0, "min_volume_burst_score": 6.0},
            },
            "order": {"slippage_cap_bps": 20, "slippage_cap_cents": 0.03},
            "sizing": {"verified_default_usd": 300, "verified_strong_usd": 500, "a_plus_max_usd": 1000},
        }
    }
    events = load_stream_events(Path(args.events_jsonl))
    print(json.dumps(replay_opening_stream(candidate, events, cfg, output_dir=Path(args.output_dir))))


if __name__ == "__main__":
    main()
