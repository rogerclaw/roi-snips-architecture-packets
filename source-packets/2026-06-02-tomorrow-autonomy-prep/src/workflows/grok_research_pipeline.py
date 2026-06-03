from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..adapters.grok_web_search import GrokWebSearchAdapter
from ..adapters.grok_x_search import GrokXSearchAdapter
from ..common.config import load_workflow_config, repo_root
from ..research.research_seed_packet import build_research_seed_packet
from ..research.grok_d_research import run_grok_d_research_tournament, run_grok_red_team
from ..research.grok_ticket_builder import create_grok_ticket_input_summary
from ..research.grok_web_verifier import run_grok_web_verification
from ..research.grok_x_heat_radar import run_grok_x_heat_radar


def run_grok_research_pipeline(
    *,
    trading_date: str | None = None,
    seed_packet: dict[str, Any] | None = None,
    x_adapter: GrokXSearchAdapter | None = None,
    web_adapter: GrokWebSearchAdapter | None = None,
    workflow_cfg: dict[str, Any] | None = None,
    sources_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trading_date = trading_date or datetime.now().strftime("%Y-%m-%d")
    workflow_cfg = workflow_cfg or load_workflow_config()
    workflow = workflow_cfg.get("workflow") or {}
    grok_cfg = workflow.get("grok_research") or {}
    source_cfg = sources_config if sources_config is not None else _load_sources_config()
    run_root = repo_root() / "runs" / trading_date
    grok_dir = run_root / "grok"
    grok_dir.mkdir(parents=True, exist_ok=True)
    seed_packet = seed_packet or _load_seed_packet(run_root)
    if not seed_packet:
        seed_packet = {"trading_date": trading_date, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "seed_packet_quality": "EMPTY"}
    _write(run_root / "research_seed_packet.json", seed_packet)

    x_heat = run_grok_x_heat_radar(
        seed_packet,
        adapter=x_adapter,
        sources_config=source_cfg,
        required=bool(grok_cfg.get("require_x_search_for_live_research", True)),
    )
    _write(grok_dir / "x_heat_radar.json", x_heat)
    web = run_grok_web_verification(
        x_heat,
        adapter=web_adapter,
        required=bool(grok_cfg.get("require_web_search_for_live_research", True)),
    )
    _write(grok_dir / "web_verification.json", web)
    tournament = run_grok_d_research_tournament(seed_packet=seed_packet, x_heat_radar=x_heat, web_verification=web)
    _write(grok_dir / "candidate_discovery_tournament.json", tournament)
    red_team = run_grok_red_team(tournament) if grok_cfg.get("red_team_enabled", True) else {"stage": "grok_red_team", "verdict": "PASS_ONLY_WITH_TAPE", "should_block_ticket": False}
    _write(grok_dir / "challenger_notes.json", red_team)
    x_threads = {
        "stage": "grok_x_threads",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "threads": [
            {"ticker": row.get("ticker"), "threads": row.get("key_threads") or [], "narrative": row.get("narrative")}
            for row in x_heat.get("candidates", [])
        ],
    }
    _write(grok_dir / "x_threads.json", x_threads)
    social_velocity = {
        "stage": "grok_social_velocity_summary",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "top_social_heat_names": [
            {
                "ticker": row.get("ticker"),
                "attention_velocity_score": row.get("attention_velocity_score"),
                "cashtag_count_estimate": row.get("cashtag_count_estimate"),
                "pump_language_score": row.get("pump_language_score"),
                "rumor_flag": row.get("rumor_flag"),
            }
            for row in x_heat.get("candidates", [])[:25]
        ],
    }
    _write(grok_dir / "social_velocity_summary.json", social_velocity)
    ticket_input_summary = create_grok_ticket_input_summary(tournament, red_team, trading_date=trading_date, model=str((workflow.get("research_llm") or {}).get("primary_model") or "grok-4.3"))
    _write(grok_dir / "ticket_input_summary.json", ticket_input_summary)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trading_date": trading_date,
        "mode": "grok_heat_discovery_for_deep_mini",
        "status": "COMPLETED_RESEARCH_ONLY",
        "authorized_ticker": None,
        "research_recommended_ticker": ticket_input_summary.get("research_recommended_ticker"),
        "can_authorize_live_trade": False,
        "artifacts": {
            "research_seed_packet": str(run_root / "research_seed_packet.json"),
            "x_heat_radar": str(grok_dir / "x_heat_radar.json"),
            "web_verification": str(grok_dir / "web_verification.json"),
            "candidate_discovery_tournament": str(grok_dir / "candidate_discovery_tournament.json"),
            "x_threads": str(grok_dir / "x_threads.json"),
            "social_velocity_summary": str(grok_dir / "social_velocity_summary.json"),
            "challenger_notes": str(grok_dir / "challenger_notes.json"),
            "ticket_input_summary": str(grok_dir / "ticket_input_summary.json"),
        },
        "ticket_valid": False,
        "ticket_blockers": ["grok_research_only_not_live_authorizer"],
        "live_authorization_rule": "Only governed OpenAI deep-mini/deep research may write the live Trade Authorization Ticket.",
    }
    _write(grok_dir / "manifest.json", manifest)
    return manifest


def _load_sources_config() -> dict[str, Any]:
    path = repo_root() / "config" / "grok_x_sources.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return data if isinstance(data, dict) else {}


def _load_seed_packet(run_root: Path) -> dict[str, Any] | None:
    for path in [run_root / "research_seed_packet.json", run_root / "normalized" / "research_seed_packet.json"]:
        if path.exists():
            try:
                parsed = json.loads(path.read_text())
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
    return _seed_packet_from_discovery_artifacts(run_root)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _rows_from_symbols(symbols: Any, *, source_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(symbols, list):
        return rows
    for symbol in symbols:
        ticker = str(symbol or "").strip().upper()
        if ticker:
            rows.append({"ticker": ticker, "symbol": ticker, "source_name": source_name})
    return rows


def _rows_from_candidates(candidates: Any, *, source_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(candidates, list):
        return rows
    for item in candidates:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or item.get("symbol") or item.get("primary_ticker") or "").strip().upper()
        if ticker:
            rows.append({**item, "ticker": ticker, "symbol": ticker, "source_name": item.get("source_name") or source_name})
    return rows


def _seed_packet_from_discovery_artifacts(run_root: Path) -> dict[str, Any] | None:
    trading_date = run_root.name
    normalized = run_root / "normalized"
    raw = run_root / "raw"
    discovered_rows = _rows_from_symbols(_load_json(normalized / "discovered_symbols.json"), source_name="legacy_discovery_symbols")
    top_raw_rows = _rows_from_candidates(_load_json(raw / "top_raw_candidates.json"), source_name="legacy_top_raw_candidates")
    broad_rows = _rows_from_candidates(_load_json(raw / "broad_ai_discovery_candidates.json"), source_name="legacy_broad_ai_discovery")
    source_lane_status = _load_json(normalized / "source_lane_status.json")
    if not any([discovered_rows, top_raw_rows, broad_rows]):
        return None
    return build_research_seed_packet(
        trading_date=trading_date,
        source_lane_status=source_lane_status if isinstance(source_lane_status, list) else [],
        high_rvol=discovered_rows,
        fresh_news=top_raw_rows,
        grok_x_social_candidates=[row for row in top_raw_rows if "social" in str(row.get("source_name") or "").lower()],
        scheduled_event_candidates=broad_rows,
    )


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Grok/X heat discovery and write research-only inputs for deep-mini.")
    parser.add_argument("--trading-date")
    parser.add_argument("--seed-packet")
    parser.add_argument("--skip-deep-mini", action="store_true", help="Accepted for legacy wrapper compatibility; Grok remains research-only.")
    parser.add_argument("--manual-symbols", default="", help="Accepted for legacy wrapper compatibility; include symbols in the seed packet.")
    args = parser.parse_args()
    seed_packet = json.loads(Path(args.seed_packet).read_text()) if args.seed_packet else None
    if seed_packet is None and args.manual_symbols:
        seed_packet = {"manual_symbols": [{"ticker": symbol.strip().upper()} for symbol in args.manual_symbols.split(",") if symbol.strip()]}
    result = run_grok_research_pipeline(trading_date=args.trading_date, seed_packet=seed_packet)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "COMPLETED_RESEARCH_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
