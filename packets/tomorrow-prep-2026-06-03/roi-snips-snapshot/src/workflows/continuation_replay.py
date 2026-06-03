from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.config import repo_root
from .opening_stream_supervisor import _load_opening_cfg, replay_opening_stream


def _read_jsonl(path: Path, event_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        row.setdefault("type", event_type)
        rows.append(row)
    return rows


def _ts(row: dict[str, Any]) -> str:
    return str(row.get("timestamp") or row.get("ts") or "")


def replay_captured_continuation(
    *,
    source_run_dir: Path,
    candidate: dict[str, Any],
    output_dir: Path,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    symbol = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
    quotes = _read_jsonl(source_run_dir / "raw_quotes.jsonl", "quote")
    trades = _read_jsonl(source_run_dir / "raw_trades.jsonl", "trade")
    events = [row for row in [*quotes, *trades] if not symbol or str(row.get("symbol") or symbol).upper() == symbol]
    if window_start:
        events = [row for row in events if _ts(row) >= window_start]
    if window_end:
        events = [row for row in events if _ts(row) <= window_end]
    events.sort(key=_ts)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = replay_opening_stream(candidate, events, _load_opening_cfg(), output_dir=output_dir)
    per_symbol = (result.get("per_symbol_decision_summary") or {}).get(symbol) or {}
    summary = {
        "target_symbol": symbol,
        "replay_window_start": window_start or (_ts(events[0]) if events else None),
        "replay_window_end": window_end or (_ts(events[-1]) if events else None),
        "raw_quote_count": result.get("raw_quote_count", 0),
        "raw_trade_count": result.get("raw_trade_count", 0),
        "decision_count": result.get("decision_count", 0),
        "best_decision": per_symbol.get("best_decision") or result.get("final_decision"),
        "first_buy_now_at": _first_buy_now_at(output_dir / "decisions.jsonl"),
        "proposal_count": result.get("proposal_count", 0),
        "no_trade_reason": (result.get("final_decision") or {}).get("reason") if result.get("proposal_count", 0) == 0 else None,
        "top_failed_predicates": per_symbol.get("top_failed_predicates") or [],
        "top_passed_predicates": per_symbol.get("top_passed_predicates") or [],
        "lifecycle_transitions": _lifecycle_transitions(per_symbol),
        "whether_09_46_style_move_caught": bool(result.get("proposal_count", 0) > 0),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_dir": str(source_run_dir),
    }
    (output_dir / "continuation_replay_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    decisions = output_dir / "decisions.jsonl"
    if decisions.exists():
        (output_dir / "continuation_decisions.jsonl").write_text(decisions.read_text())
    return summary


def _first_buy_now_at(decisions_path: Path) -> str | None:
    if not decisions_path.exists():
        return None
    for line in decisions_path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        decision = row.get("decision") or {}
        if decision.get("action") == "BUY_NOW":
            return ((row.get("features") or {}).get("latest_trade_timestamp") or (row.get("features") or {}).get("latest_quote_timestamp"))
    return None


def _lifecycle_transitions(per_symbol: dict[str, Any]) -> list[str]:
    state = per_symbol.get("lifecycle_state")
    if not state:
        return []
    if state == "OPENING_CONTINUATION_ACTIVE":
        return ["SECOND_LEG_WATCH", "OPENING_CONTINUATION_ACTIVE"]
    if state == "NO_TRADE_EXTENDED":
        return ["SECOND_LEG_WATCH", "NO_TRADE_EXTENDED"]
    return ["SECOND_LEG_WATCH", str(state)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay captured continuation tape")
    parser.add_argument("--source-run-dir", required=True)
    parser.add_argument("--candidate-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate_json).read_text())
    summary = replay_captured_continuation(
        source_run_dir=Path(args.source_run_dir),
        candidate=candidate,
        output_dir=Path(args.output_dir),
        window_start=args.window_start,
        window_end=args.window_end,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
