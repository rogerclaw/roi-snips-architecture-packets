#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


def _trade_date() -> str:
    override = os.getenv("ROI_SNIPS_TRADE_DATE", "").strip()
    if override:
        return override
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _line_count(path: str | None) -> int:
    if not path:
        return 0
    p = Path(path)
    if not p.exists():
        return 0
    return sum(1 for line in p.read_text(errors="replace").splitlines() if line.strip())


def _run_step(name: str, command: list[str], *, timeout: int, env: dict[str, str]) -> dict[str, object]:
    started = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        status = "ok" if completed.returncode == 0 else "failed"
        return {
            "name": name,
            "status": status,
            "returncode": completed.returncode,
            "timeout_seconds": timeout,
            "started_at_utc": started.isoformat(),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "status": "timeout",
            "returncode": None,
            "timeout_seconds": timeout,
            "started_at_utc": started.isoformat(),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def _skipped_step(name: str, reason: str) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "name": name,
        "status": "ok",
        "returncode": 0,
        "timeout_seconds": 0,
        "started_at_utc": now,
        "finished_at_utc": now,
        "stdout_tail": json.dumps({"status": "skipped", "reason": reason}),
        "stderr_tail": "",
    }


def _load_json(path: Path) -> object | None:
    if not path.exists() or not path.read_text(errors="replace").strip():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _latest_stream_summary(trade_date: str) -> dict[str, object]:
    runs_dir = ROOT / "reports" / "live_monitor" / "runs"
    candidates = sorted(runs_dir.glob(f"opening_stream_{trade_date}_*/final_summary.json")) if runs_dir.exists() else []
    if not candidates:
        return {"ok": False, "reason": "opening_stream_summary_missing"}
    path = candidates[-1]
    summary = _load_json(path)
    if not isinstance(summary, dict):
        return {"ok": False, "reason": "opening_stream_summary_unreadable", "summary_path": str(path)}
    raw_quote_count = _line_count(summary.get("raw_quotes"))
    raw_trade_count = _line_count(summary.get("raw_trades"))
    decision_count = _line_count(summary.get("decisions"))
    stream_captured = raw_quote_count > 0 and raw_trade_count > 0 and decision_count > 0
    return {
        "ok": True,
        "summary_path": str(path),
        "output_dir": str(path.parent),
        "stream_captured": stream_captured,
        "stream_capture_started": bool(summary.get("stream_capture_started", True)),
        "stream_capture_completed": bool(summary.get("stream_capture_completed", stream_captured)),
        "orders_submitted": summary.get("orders_submitted"),
        "proposal_count": summary.get("proposal_count"),
        "blocked_proposal_count": summary.get("blocked_proposal_count"),
        "fired_symbols": summary.get("fired_symbols"),
        "stopped_by_timer": summary.get("stopped_by_timer"),
        "max_seconds": summary.get("max_seconds"),
        "raw_quote_count": raw_quote_count,
        "raw_trade_count": raw_trade_count,
        "decision_count": decision_count,
        "decisions_count": decision_count,
        "proposal_line_count": _line_count(summary.get("proposals")),
        "stream_status": summary.get("stream_status"),
        "reason": summary.get("reason"),
    }


def _stream_required_failure(stream: dict[str, object], *, stream_required: bool) -> bool:
    return bool(
        stream_required
        and (
            stream.get("reason") == "stream_skipped"
            or not stream.get("stream_capture_started")
            or not stream.get("stream_capture_completed")
            or not stream.get("stream_captured")
            or int(stream.get("raw_quote_count") or 0) <= 0
            or int(stream.get("raw_trade_count") or 0) <= 0
            or int(stream.get("decision_count") or stream.get("decisions_count") or 0) <= 0
            or stream.get("orders_submitted") is not False
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded no-order next-open Roi Snips validation.")
    parser.add_argument("--skip-stream", action="store_true", help="Run research/premarket/readiness only.")
    parser.add_argument("--research-timeout", type=int, default=int(os.getenv("ROI_SNIPS_RESEARCH_TIMEOUT_SECONDS", "180")))
    parser.add_argument("--premarket-timeout", type=int, default=int(os.getenv("ROI_SNIPS_PREMARKET_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--readiness-timeout", type=int, default=int(os.getenv("ROI_SNIPS_READINESS_TIMEOUT_SECONDS", "60")))
    parser.add_argument("--stream-timeout", type=int, default=int(os.getenv("ROI_SNIPS_SHADOW_COMMAND_TIMEOUT_SECONDS", "1080")))
    parser.add_argument("--stream-max-seconds", type=int, default=int(os.getenv("ROI_SNIPS_OPENING_STREAM_MAX_SECONDS", "900")))
    parser.add_argument("--stream-required", action=argparse.BooleanOptionalAction, default=None)
    args = parser.parse_args()

    trade_date = _trade_date()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(ROOT)
    env["ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION"] = "false"
    env["ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION"] = "false"
    env["ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT"] = "true"
    env["ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW"] = "true"
    env["ROI_SNIPS_RUN_CONTINUATION_MONITOR"] = "true"
    env["SMOKE_SKIP_DEEP_MINI_NOT_FOR_LIVE_SELECTION"] = "true"
    env.setdefault("ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS", "8")
    env.setdefault("STOCKTWITS_TIMEOUT_SECONDS", "3")
    env.setdefault("ROI_SNIPS_OPENING_STREAM_MAX_SECONDS", str(args.stream_max_seconds))

    steps: list[dict[str, object]] = []
    brokerless_shadow = (
        env.get("ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT", "").strip().lower() == "true"
        and env.get("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "").strip().lower() not in {"1", "true", "yes", "on"}
    )
    steps.append(_run_step("research_skip_deep_mini_smoke_not_for_live_selection", [str(ROOT / ".venv/bin/python"), "-m", "src.workflows.research_pipeline", "--skip-deep-mini"], timeout=args.research_timeout, env=env))
    if steps[-1]["status"] == "ok":
        steps.append(_run_step("premarket_pipeline", [str(ROOT / ".venv/bin/python"), "-m", "src.workflows.premarket_pipeline"], timeout=args.premarket_timeout, env=env))
    if steps[-1]["status"] == "ok":
        if brokerless_shadow:
            steps.append(_skipped_step("broker_readiness_skipped_for_brokerless_shadow", "no_order_market_data_validation_must_not_query_broker_state"))
        else:
            steps.append(_run_step("live_readiness", ["scripts/check_live_readiness.sh"], timeout=args.readiness_timeout, env=env))
    if steps[-1]["status"] == "ok":
        if brokerless_shadow:
            steps.append(_skipped_step("opening_bell_readiness_skipped_for_brokerless_shadow", "readiness_only_path_inspects_broker_state"))
        else:
            opening = _run_step("opening_bell_readiness_allow_non_green", ["scripts/check_opening_bell_readiness.sh"], timeout=args.readiness_timeout, env=env)
            if opening["status"] == "failed":
                opening["status"] = "non_green_allowed_for_shadow"
            steps.append(opening)
    if not args.skip_stream and steps[-1]["status"] in {"ok", "non_green_allowed_for_shadow"}:
        steps.append(_run_step("opening_stream_shadow", ["scripts/run_opening_stream_shadow.sh"], timeout=args.stream_timeout, env=env))

    artifacts_root = ROOT / "reports" / "live_monitor"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    stream_required = (not args.skip_stream) if args.stream_required is None else bool(args.stream_required)
    shadow_mode = "PRE_OPEN_READINESS_ONLY" if args.skip_stream else "OPENING_STREAM_SHADOW"
    stream = {"ok": False, "reason": "stream_skipped", "stream_captured": False, "stream_capture_started": False, "stream_capture_completed": False} if args.skip_stream else _latest_stream_summary(trade_date)
    stream_failure = _stream_required_failure(stream, stream_required=stream_required)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trade_date": trade_date,
        "mode": "next_open_no_order_shadow_validation",
        "shadow_mode": shadow_mode,
        "stream_required": stream_required,
        "orders_allowed": False,
        "orders_submitted": False,
        "broker_account_inspected": False,
        "broker_orders_inspected": False,
        "broker_positions_inspected": False,
        "steps": steps,
        "stream": stream,
        "status": "SHADOW_INVALID" if stream_failure else "OK",
        "failure_class": "INTERNAL_FAILURE" if stream_failure else None,
        "all_steps_ok_or_shadow_allowed": all(step["status"] in {"ok", "non_green_allowed_for_shadow"} for step in steps) and not stream_failure,
    }
    out_path = artifacts_root / f"next_open_shadow_validation_{trade_date}.json"
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps({"summary_path": str(out_path), **summary}, indent=2, sort_keys=True))
    if not summary["all_steps_ok_or_shadow_allowed"]:
        return 1
    if stream_failure:
        return 1
    if not args.skip_stream and not stream.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
