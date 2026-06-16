from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_gate import evaluate_morning_readiness


ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _latest_stream_summary(trade_date: str, *, root: Path = ROOT) -> dict[str, Any]:
    runs_dir = root / "reports" / "live_monitor" / "runs"
    candidates = sorted(runs_dir.glob(f"opening_stream_{trade_date}_*/final_summary.json")) if runs_dir.exists() else []
    return _load_json(candidates[-1]) if candidates else {}


def build_morning_readiness(
    *,
    trade_date: str,
    root: Path = ROOT,
    canary_path: Path | None = None,
    same_day_packet_path: Path | None = None,
    source_lane_status_path: Path | None = None,
    stream_summary_path: Path | None = None,
    stream_required: bool = True,
    proof_scope: str = "MARKET_OPEN_READINESS",
) -> dict[str, Any]:
    canary_path = canary_path or root / "reports" / "readiness" / f"canary_{trade_date}.json"
    same_day_packet_path = same_day_packet_path or root / "reports" / "live_monitor" / f"next_open_shadow_validation_{trade_date}.json"
    source_lane_status_path = source_lane_status_path or root / "runs" / trade_date / "normalized" / "source_lane_status.json"
    stream_summary = _load_json(stream_summary_path) if stream_summary_path else _latest_stream_summary(trade_date, root=root)
    same_day_packet = _load_json(same_day_packet_path)

    symbols = same_day_packet.get("symbols") or []
    if not symbols:
        stream = same_day_packet.get("stream") or {}
        fired = stream.get("fired_symbols") or []
        symbols = fired if fired else same_day_packet.get("discovered_symbols") or []

    artifacts = {
        "canary": _load_json(canary_path),
        "same_day_packet": same_day_packet,
        "source_lane_status": _load_json(source_lane_status_path),
        "stream_summary": stream_summary or same_day_packet.get("stream") or {},
        "symbols": symbols,
        "broad_discovery": same_day_packet.get("broad_discovery") or {},
        "candidate_tournament": same_day_packet.get("candidate_tournament") or {},
        "research_war_room": same_day_packet.get("research_war_room") or {},
        "orders_submitted": same_day_packet.get("orders_submitted"),
        "orders_previewed": same_day_packet.get("orders_previewed"),
        "orders_canceled": same_day_packet.get("orders_canceled"),
        "broker_account_inspected": same_day_packet.get("broker_account_inspected"),
        "broker_orders_inspected": same_day_packet.get("broker_orders_inspected"),
        "broker_positions_inspected": same_day_packet.get("broker_positions_inspected"),
    }
    readiness = evaluate_morning_readiness(artifacts, stream_required=stream_required, requested_proof_scope=proof_scope)
    result = readiness.to_dict()
    result.update(
        {
            "date": trade_date,
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "artifact_paths": {
                "canary": str(canary_path),
                "same_day_packet": str(same_day_packet_path),
                "source_lane_status": str(source_lane_status_path),
                "stream_summary": str(stream_summary_path) if stream_summary_path else "latest_for_trade_date",
            },
        }
    )
    return result


def write_morning_readiness(output_path: Path, **kwargs: Any) -> dict[str, Any]:
    result = build_morning_readiness(**kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Roi Snips brokerless morning readiness artifacts.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--canary")
    parser.add_argument("--same-day-packet")
    parser.add_argument("--source-lane-status")
    parser.add_argument("--stream-summary")
    parser.add_argument("--no-stream-required", action="store_true")
    parser.add_argument("--proof-scope", default="MARKET_OPEN_READINESS")
    args = parser.parse_args()

    result = write_morning_readiness(
        Path(args.output),
        trade_date=args.date,
        root=ROOT,
        canary_path=Path(args.canary) if args.canary else None,
        same_day_packet_path=Path(args.same_day_packet) if args.same_day_packet else None,
        source_lane_status_path=Path(args.source_lane_status) if args.source_lane_status else None,
        stream_summary_path=Path(args.stream_summary) if args.stream_summary else None,
        stream_required=not args.no_stream_required,
        proof_scope=args.proof_scope,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready_for_no_order"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
