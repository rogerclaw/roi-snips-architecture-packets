#!/usr/bin/env python3
"""Broker-safe Roi Snips readiness checks.

This script intentionally inspects only local files and OpenClaw cron metadata
captured by `openclaw cron list --json`. It must not call broker APIs, preview
orders, place orders, cancel orders, replace orders, or mutate live guard files.
"""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = Path(os.environ.get("ROI_SNIPS_RUNTIME_ROOT", "/Users/rogerclaw/.openclaw/workspace/roi-snips")).resolve()


EXPECTED_SHELL_CRON_NEEDLES = [
    "45 4 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "scripts/roi_snips_morning_canary.sh",
    "0 5 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    ".venv/bin/python -m src.workflows.research_pipeline --discovery-only",
    "10 5 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "45 5 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "0 6 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "10 6 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "scripts/run_live_trade_ready_premarket.sh",
    "20 6 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "25 6 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "scripts/run_final_live_arming_gate.sh",
    "28 6 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "scripts/run_live_opening_trade_ready.sh",
    "45 12 * * 1-5 cd /Users/rogerclaw/.openclaw/workspace/roi-snips",
    "scripts/run_live_force_flat.sh",
]


REQUIRED_WORKFLOW_NEEDLES = [
    "primary_provider: openai",
    "primary_mode: deep_mini",
    "primary_role: live_stock_picker",
    "grok_role: social_heat_discovery_and_challenger",
    "require_for_live_research: true",
    "require_grok_for_live_research: false",
]


REQUIRED_LIVE_NEEDLES = [
    "provider: webull",
    "base_url: https://api.webull.com",
    "require_trade_authorization_ticket: true",
    "authorized_ticket_only_execution: true",
    "deep_mini_required_for_live_research: true",
    "grok_required_for_live_research: false",
    "grok_only_ticket_executable_allowed: false",
    "deterministic_fallback_executable_allowed: false",
]


REQUIRED_PREMARKET_NEEDLES = [
    "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false",
    "ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false",
]


REQUIRED_LIVE_WRAPPER_NEEDLES = [
    "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true",
    "ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false",
    "WEBULL_ENVIRONMENT=live",
]


def fail(message: str) -> None:
    print(f"FAIL {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"PASS {message}")


def require_file_contains(path: str, needles: list[str]) -> None:
    file_path = ROOT / path
    text = file_path.read_text()
    missing = [needle for needle in needles if needle not in text]
    if missing:
        fail(f"{path} missing {missing}")
    ok(f"{path} contains required invariants")


def check_cron() -> None:
    subprocess.check_output(["openclaw", "cron", "list", "--json"], text=True)
    ok("OpenClaw cron metadata surface is reachable")


def check_shell_crontab() -> None:
    raw = subprocess.check_output(["crontab", "-l"], text=True)
    missing = [needle for needle in EXPECTED_SHELL_CRON_NEEDLES if needle not in raw]
    if missing:
        fail(f"shell crontab missing {missing}")
    ok("weekday shell crontab contains canary, discovery, premarket retries, final arming, opening, and force-flat")


def check_guard_posture() -> None:
    guard_root = RUNTIME_ROOT if RUNTIME_ROOT.exists() else ROOT
    disable = guard_root / "state" / "DISABLE_NEW_ENTRIES"
    if not disable.exists():
        fail(f"{guard_root}/state/DISABLE_NEW_ENTRIES missing before deterministic gate")
    if (guard_root / "state" / "LIVE_ARMED").exists():
        fail(f"{guard_root}/state/LIVE_ARMED exists before deterministic gate")
    if (guard_root / "state" / "KILL_SWITCH").exists():
        fail(f"{guard_root}/state/KILL_SWITCH exists")
    ok("local guard posture is fail-closed before deterministic live gate")


def main() -> int:
    require_file_contains("config/workflow.yaml", REQUIRED_WORKFLOW_NEEDLES)
    require_file_contains("configs/live.yaml", REQUIRED_LIVE_NEEDLES)
    require_file_contains("scripts/run_live_trade_ready_premarket.sh", REQUIRED_PREMARKET_NEEDLES)
    require_file_contains("scripts/run_final_live_arming_gate.sh", REQUIRED_LIVE_WRAPPER_NEEDLES)
    require_file_contains("scripts/run_live_opening_trade_ready.sh", REQUIRED_LIVE_WRAPPER_NEEDLES)
    require_file_contains("scripts/run_live_force_flat.sh", REQUIRED_LIVE_WRAPPER_NEEDLES)
    check_cron()
    check_shell_crontab()
    check_guard_posture()
    return 0


if __name__ == "__main__":
    sys.exit(main())
