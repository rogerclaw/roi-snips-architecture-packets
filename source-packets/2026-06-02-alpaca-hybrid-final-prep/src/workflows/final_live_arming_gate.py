"""Conditional final live arming gate for the scheduled morning run."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..common.config import load_live_config, repo_root
from ..common.runtime_state import activate_flag, active_guards, clear_flag
from ..research.trade_authorization_ticket import load_today_ticket, validate_ticket
from .opening_bell_monitor import check_opening_bell_readiness


def _trade_date() -> str:
    override = os.getenv("ROI_SNIPS_TRADE_DATE", "").strip()
    if override:
        return override
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _output_path(root: Path, trade_date: str) -> Path:
    return root / "reports" / "readiness" / f"final_live_arming_gate_{trade_date}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _deep_mini_reached_blockers(root: Path, trade_date: str) -> list[str]:
    status_path = root / "reports" / "live_monitor" / "live_trade_ready" / "research_latest.status.json"
    if not status_path.exists():
        return ["premarket_research_never_reached_deep_mini"]
    try:
        status = json.loads(status_path.read_text())
    except Exception:
        return ["premarket_research_never_reached_deep_mini"]
    if not isinstance(status, dict):
        return ["premarket_research_never_reached_deep_mini"]
    if status.get("trade_date") != trade_date:
        return ["premarket_research_never_reached_deep_mini"]
    if status.get("step") != "governed_deep_research_pipeline":
        return ["premarket_research_never_reached_deep_mini"]
    if status.get("exit_code") != 0:
        return ["premarket_research_never_reached_deep_mini"]
    if status.get("deep_mini_required") is not True:
        return ["premarket_research_never_reached_deep_mini"]
    if status.get("deep_mini_reached") is not True:
        return ["premarket_research_never_reached_deep_mini"]
    return []


def run_final_live_arming_gate(*, execute: bool = True) -> dict[str, Any]:
    root = repo_root()
    trade_date = _trade_date()
    cfg = load_live_config()
    try:
        readiness = check_opening_bell_readiness(ignore_arm_guards=True, inspect_broker_state=execute)
    except TypeError:
        readiness = check_opening_bell_readiness(ignore_arm_guards=True)
    blockers = list(readiness.get("opening_bell_blockers") or [])
    if execute and (readiness.get("readiness") or {}).get("broker_access_attempted") is False:
        blockers.append("brokerless_proof_not_live_readiness")
    blockers.extend(_deep_mini_reached_blockers(root, trade_date))
    ticket = load_today_ticket(root, trade_date)
    ticket_validation = validate_ticket(ticket)
    if not ticket_validation.valid:
        blockers.extend(ticket_validation.blockers)
    green = readiness.get("status") == "GREEN" and not blockers and ticket_validation.valid
    live_env_enabled = os.getenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "").strip().lower() in {"1", "true", "yes", "on"}
    paper_env_enabled = os.getenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "").strip().lower() in {"1", "true", "yes", "on"}

    armed = False
    action = "dry_run"
    if execute:
        if green and live_env_enabled and not paper_env_enabled:
            activate_flag("live_armed", reason=f"final_live_arming_gate_green:{trade_date}", cfg=cfg)
            clear_flag("disable_entries", cfg)
            armed = True
            action = "armed_live"
        else:
            clear_flag("live_armed", cfg)
            activate_flag("disable_entries", reason=f"final_live_arming_gate_blocked:{trade_date}", cfg=cfg)
            action = "held_fail_closed"

    payload = {
        "trade_date": trade_date,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execute": execute,
        "verdict": "GO" if armed else ("READY_NOT_ARMED_DRY_RUN" if green else "NO_GO"),
        "action": action,
        "armed_live": armed,
        "pre_open_standby_override": False,
        "authorized_ticker": (ticket or {}).get("authorized_ticker"),
        "authorized_strategy": (ticket or {}).get("authorized_strategy") or (ticket or {}).get("strategy"),
        "ticket_valid": ticket_validation.valid,
        "ticket_status": ticket_validation.status,
        "ticket_blockers": ticket_validation.blockers,
        "live_order_env_enabled": live_env_enabled,
        "paper_order_env_enabled": paper_env_enabled,
        "readiness_status": readiness.get("status"),
        "blockers": blockers,
        "ignored_arm_guard_blockers": readiness.get("ignored_arm_guard_blockers") or [],
        "primary_candidate": readiness.get("primary_candidate"),
        "candidate_specific_readiness": readiness.get("candidate_specific_readiness"),
        "guards_after": active_guards(cfg),
        "orders_submitted_now": False,
        "orders_previewed_now": False,
        "readiness": readiness,
    }
    _write_json(_output_path(root, trade_date), payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Conditionally arm Roi Snips live trading after the final morning readiness gate.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_final_live_arming_gate(execute=not args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("verdict") == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
