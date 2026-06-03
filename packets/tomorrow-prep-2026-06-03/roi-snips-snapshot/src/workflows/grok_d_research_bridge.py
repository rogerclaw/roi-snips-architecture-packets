from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..adapters.grok_search import GrokSearchAdapter
from .deep_mini_bridge import (
    DEEP_MINI_REQUIRED_BLOCKER,
    build_deep_mini_brief,
    parse_deep_mini_output,
)


GROK_REQUIRED_BLOCKER = "grok_d_research_required_for_live_research_not_completed"


@dataclass
class GrokDResearchRunArtifacts:
    status: str
    success: bool
    prompt_path: str | None = None
    summary_path: str | None = None
    raw_output_path: str | None = None
    structured_packet_path: str | None = None
    structured_packet: dict[str, Any] | None = None
    route_chosen: str = "grok_d_research"
    error: str | None = None
    runner_stdout: str | None = None
    runner_stderr: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def grok_required_for_live_research(deep_cfg: dict[str, Any] | None = None, research_mode: dict[str, Any] | None = None) -> bool:
    deep_cfg = deep_cfg or {}
    research_mode = research_mode or {}
    if research_mode.get("grok_required_for_live_research") is True:
        return True
    if deep_cfg.get("require_grok_for_live_research") is True:
        return True
    return str(deep_cfg.get("mode") or "").strip() == "grok_d_research" and deep_cfg.get("require_for_live_research") is True


def write_grok_d_research_input(shortlist: list[dict[str, Any]], context: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}_{time.time_ns()}_{uuid.uuid4().hex[:8]}"
    brief = "\n\n".join(
        [
            "You are the Grok-first Roi Snips D-research authorizer.",
            "Use X/social/live-web discovery aggressively, but do not treat social hype as validation by itself.",
            "Return one decisive best idea or NO_TRADE. Backups are research-only. Deterministic fallback is never executable.",
            build_deep_mini_brief(shortlist, {**context, "route_chosen": "grok_d_research"}),
        ]
    )
    path = output_dir / f"grok_d_research_{run_id}.md"
    path.write_text(brief)
    (output_dir / "grok_d_research_input.md").write_text(brief)
    return path


def _symbols_from_shortlist(shortlist: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    for row in shortlist:
        symbol = str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).upper().strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _row_for_symbol(symbol: str | None, shortlist: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not symbol:
        return None
    wanted = symbol.upper()
    for row in shortlist:
        row_symbol = str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).upper().strip()
        if row_symbol == wanted:
            return row
    return None


def _has_non_social_validation(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    cluster = row.get("cluster") or {}
    scorecard = row.get("research_scorecard") or {}
    if cluster.get("official_sources") or cluster.get("structured_sources"):
        return True
    if int(scorecard.get("official_confirmation_count") or 0) > 0:
        return True
    if int(scorecard.get("structured_confirmation_count") or 0) > 0:
        return True
    return False


def _packet_from_json(payload: dict[str, Any], shortlist: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    executor_output = json.dumps(payload, indent=2, sort_keys=True)
    packet = parse_deep_mini_output(executor_output, shortlist, {**context, "route_chosen": "grok_d_research"}).to_dict()
    packet["source_mode"] = "governed_grok_d_research"
    packet["route_chosen"] = "grok_d_research"
    packet["grok_model"] = payload.get("model")
    packet["grok_citations"] = payload.get("citations") or []
    packet["deterministic_fallback_executable_allowed"] = False
    packet["buy_now_allowed"] = False
    selected_row = _row_for_symbol(packet.get("best_pick"), shortlist)
    if packet.get("best_pick") and not _has_non_social_validation(selected_row):
        packet.setdefault("caveats", []).append("grok_social_only_not_authorizing")
    packet["trade_authorization"] = {
        "authorized": bool(packet.get("best_pick")) and not packet.get("caveats"),
        "ticker": packet.get("best_pick"),
        "authorized_strategy": payload.get("authorized_strategy") or payload.get("strategy") or "SECOND_LEG_CONTINUATION",
        "status": "AUTHORIZED_ONE_TICKER" if packet.get("best_pick") and not packet.get("caveats") else "NO_TRADE_NOT_AUTHORIZED",
        "blockers": [] if packet.get("best_pick") and not packet.get("caveats") else list(packet.get("caveats") or [GROK_REQUIRED_BLOCKER]),
        "one_ticker_only": True,
        "deterministic_fallback_executable_allowed": False,
        "backup_execution_allowed": False,
        "research_brain": "grok_first_d_research",
    }
    return packet


def run_governed_grok_d_research(
    shortlist: list[dict[str, Any]],
    context: dict[str, Any],
    output_dir: Path,
    deep_cfg: dict[str, Any] | None = None,
    adapter: GrokSearchAdapter | None = None,
) -> GrokDResearchRunArtifacts:
    deep_cfg = deep_cfg or {}
    prompt_path = write_grok_d_research_input(shortlist, context, output_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}_{time.time_ns()}_{uuid.uuid4().hex[:8]}"
    summary_path = output_dir / f"grok_d_research_summary_{run_id}.json"
    raw_output_path = output_dir / f"grok_d_research_output_{run_id}.json"
    structured_packet_path = output_dir / f"grok_d_research_packet_{run_id}.json"
    adapter = adapter or GrokSearchAdapter(timeout_seconds=int(deep_cfg.get("timeout_seconds", 900)))
    symbols = _symbols_from_shortlist(shortlist)
    query = " ".join([f"${symbol}" for symbol in symbols[:12]]) + " stock catalyst X social velocity premarket live web today"
    result = adapter.search(query.strip(), limit=int(deep_cfg.get("grok_search_limit", 10)))
    raw_output_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("ok"):
        summary = {
            "status": "failed",
            "success": False,
            "route_chosen": "grok_d_research",
            "error": result.get("reason") or "grok_d_research_failed",
            "prompt_path": str(prompt_path),
            "raw_output_path": str(raw_output_path),
        }
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
        return GrokDResearchRunArtifacts(
            status="failed",
            success=False,
            prompt_path=str(prompt_path),
            summary_path=str(summary_path),
            raw_output_path=str(raw_output_path),
            error=str(summary["error"]),
            runner_stdout=json.dumps(result, sort_keys=True),
        )

    structured = _packet_from_json(
        {
            "ticker": result.get("best_pick") or _symbols_from_shortlist(shortlist)[0] if shortlist else None,
            "exact_catalyst": result.get("content") or "Grok live-web/X synthesis",
            "suggested_buy_zone": "Wait for deterministic live tape confirmation; research cannot buy now.",
            "same_day_upside_target": "Use deterministic tape-derived target after open.",
            "one_to_three_day_upside_target": "Use deterministic tape-derived 1-3 day target after open.",
            "thesis_break_level": "Invalidated by failed tape confirmation, VWAP loss, or catalyst contradiction.",
            "profit_taking_triggers": ["Take profit into volume-backed spikes; never rely on social hype alone."],
            "danger_signals": ["Social-only pump with no official or structured confirmation.", "Spread/liquidity deterioration."],
            "strategy": "SECOND_LEG_CONTINUATION",
            "model": result.get("model"),
            "citations": result.get("citations") or [],
        },
        shortlist,
        context,
    )
    structured_packet_path.write_text(json.dumps(structured, indent=2, sort_keys=True))
    summary = {
        "status": "completed",
        "success": True,
        "route_chosen": "grok_d_research",
        "provider": result.get("provider"),
        "model": result.get("model"),
        "citations": result.get("citations") or [],
        "prompt_path": str(prompt_path),
        "raw_output_path": str(raw_output_path),
        "structured_packet_path": str(structured_packet_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return GrokDResearchRunArtifacts(
        status="completed",
        success=True,
        prompt_path=str(prompt_path),
        summary_path=str(summary_path),
        raw_output_path=str(raw_output_path),
        structured_packet_path=str(structured_packet_path),
        structured_packet=structured,
        runner_stdout=json.dumps(result, sort_keys=True),
    )


def legacy_deep_mini_blocker_for_grok() -> str:
    return DEEP_MINI_REQUIRED_BLOCKER
