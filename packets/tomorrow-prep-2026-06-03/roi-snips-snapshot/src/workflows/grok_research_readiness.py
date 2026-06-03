from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..adapters.grok_web_search import GrokWebSearchAdapter
from ..adapters.grok_x_search import GrokXSearchAdapter
from ..adapters.xai_responses import XAIResponsesAdapter, parse_json_object
from ..common.config import repo_root
from ..research.grok_prompt_pack import prompt_pack_status


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".canary_write_probe"
        probe.write_text("ok")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def run_grok_research_readiness(*, trading_date: str | None = None, probe_tools: bool = True) -> dict[str, Any]:
    trading_date = trading_date or datetime.now().strftime("%Y-%m-%d")
    grok_required = _env_truthy("ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH")
    adapter = XAIResponsesAdapter()
    artifact_dir = repo_root() / "runs" / trading_date / "grok"
    prompt_status = prompt_pack_status()
    checks: dict[str, Any] = {
        "xai_api_key_present": adapter.has_api_key,
        "openclaw_grok_search_enabled": _env_truthy("ROI_SNIPS_GROK_USE_OPENCLAW_SEARCH", "true"),
        "grok_model_configured": bool(adapter.model),
        "structured_output_parse_usable": parse_json_object('{"status":"ok"}') == {"status": "ok"},
        "artifact_dir_writable": _writable(artifact_dir),
        "prompt_pack": prompt_status,
        "order_functions_touched": False,
    }
    if probe_tools:
        checks["x_search"] = GrokXSearchAdapter(adapter).readiness_probe()
        checks["web_search"] = GrokWebSearchAdapter(adapter).readiness_probe()
    else:
        checks["x_search"] = {"ok": None, "reason": "probe_skipped"}
        checks["web_search"] = {"ok": None, "reason": "probe_skipped"}

    blockers: list[str] = []
    warnings: list[str] = []
    if (
        not checks["xai_api_key_present"]
        and not checks["openclaw_grok_search_enabled"]
        and not _env_truthy("ROI_SNIPS_GROK_CANARY_ALLOW_OPENCLAW_AUTH")
    ):
        blockers.append("xai_api_key_missing")
    if not checks["grok_model_configured"]:
        blockers.append("grok_model_missing")
    if prompt_status["missing"]:
        message = "grok_hybrid_prompt_pack_incomplete"
        (blockers if grok_required else warnings).append(message)
    if not checks["structured_output_parse_usable"]:
        blockers.append("structured_output_parse_unusable")
    if not checks["artifact_dir_writable"]:
        blockers.append("artifact_dir_not_writable")
    if probe_tools and checks["x_search"].get("ok") is not True:
        (blockers if grok_required else warnings).append("x_search_unavailable")
    if probe_tools and checks["web_search"].get("ok") is not True:
        (blockers if grok_required else warnings).append("web_search_unavailable")

    if blockers:
        status = "FAIL_REQUIRED_GROK_UNAVAILABLE" if grok_required else "FAIL"
    elif warnings:
        status = "DEGRADED_OPTIONAL_GROK_UNAVAILABLE"
    else:
        status = "PASS"
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trading_date": trading_date,
        "status": status,
        "grok_required_for_live": grok_required,
        "hybrid_architecture": True,
        "old_grok_authorizer_prompts_required": False,
        "current_prompt_pack_ok": bool(prompt_status["ok"]),
        "warnings": warnings,
        "blockers": blockers,
        "checks": checks,
        "failure_action": "NO_TRADE_RESEARCH_INCOMPLETE" if blockers else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check hybrid Grok heat/challenger readiness.")
    parser.add_argument("--trading-date")
    parser.add_argument("--no-probe-tools", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_grok_research_readiness(trading_date=args.trading_date, probe_tools=not args.no_probe_tools)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["status"].startswith("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
