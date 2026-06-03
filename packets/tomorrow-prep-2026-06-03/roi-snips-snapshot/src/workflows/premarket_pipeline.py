"""Premarket pipeline driven by dynamic research artifacts and late execution gating."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..adapters.alpaca_clock import AlpacaClockAdapter
from ..common.config import load_live_config, load_workflow_config, repo_root
from ..research import lifecycle as lc
from ..research.market_overlay import build_market_overlays, classify_anti_chase_state
from ..research.source_lane_status import build_source_lane_status
from ..research.storage import ResearchRunStorage
from ..research.trade_authorization import authorize_one_ticker_trade
from ..research.trade_authorization_ticket import load_today_ticket, ticket_from_final_packet, validate_ticket
from .deep_mini_bridge import DEEP_MINI_REQUIRED_BLOCKER, deep_mini_required_for_live_research
from .research_pipeline import ResearchPipeline, _manual_symbol_overrides

MEGACAP_DEFAULT_TICKERS = {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"}


def _today_storage() -> ResearchRunStorage:
    return ResearchRunStorage(trading_day=os.getenv("ROI_SNIPS_TRADE_DATE", "").strip() or datetime.now().strftime("%Y-%m-%d"))


def _load_json_if_exists(storage: ResearchRunStorage, relative_path: str, default: Any) -> Any:
    path = storage.path(relative_path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _overlay_dict_is_fresh(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    observed_at = payload.get("observed_at")
    if not observed_at:
        return False
    try:
        observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
    except Exception:
        return False
    age_seconds = (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    return age_seconds <= 20 * 60


def _tier_watchlist(research_ranked: list[dict[str, Any]], execution_watchlist: list[dict[str, Any]], watch_cfg: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    counts = (watch_cfg.get("tier_count") or {}) if isinstance(watch_cfg, dict) else {}
    a_count = int(counts.get("A", 3))
    b_count = int(counts.get("B", 5))
    c_count = int(counts.get("C", 8))

    unique_execution = _unique_rows_by_symbol(execution_watchlist)
    unique_research = _unique_rows_by_symbol(research_ranked)
    execution_symbols = {_row_symbol(row) for row in unique_execution}
    a_tier = unique_execution[:a_count]
    b_tier = [row for row in unique_research if _row_symbol(row) not in execution_symbols][:b_count]
    used_symbols = execution_symbols | {_row_symbol(row) for row in b_tier}
    c_tier = [row for row in unique_research if _row_symbol(row) not in used_symbols][:c_count]
    if a_tier:
        primary_lanes = set((a_tier[0].get("lane_tags") or []) + ((a_tier[0].get("research_scorecard") or {}).get("lane_tags") or []))
        if "POLICY_THEME_RUNNER_ARCHETYPE" in primary_lanes or "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE" in primary_lanes:
            def backup_key(row: dict[str, Any]) -> tuple[int, float]:
                symbol = _row_symbol(row)
                lanes = set((row.get("lane_tags") or []) + ((row.get("research_scorecard") or {}).get("lane_tags") or []))
                same_style = symbol not in MEGACAP_DEFAULT_TICKERS and ("POLICY_THEME_RUNNER_ARCHETYPE" in lanes or "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE" in lanes or float(row.get("hyper_trade_score") or 0.0) >= 2.0)
                return (0 if same_style else (2 if symbol in MEGACAP_DEFAULT_TICKERS else 1), -float(row.get("hyper_trade_score") or row.get("research_priority_score") or 0.0))

            b_tier.sort(key=backup_key)
            c_tier.sort(key=backup_key)
    return {"A": a_tier, "B": b_tier, "C": c_tier}


def _row_symbol(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker")) or "").upper().strip()


def _unique_rows_by_symbol(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        symbol = _row_symbol(row)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        out.append(row)
    return out


def _render_watch_row(row: dict[str, Any]) -> dict[str, Any]:
    cluster = row.get("cluster") or {}
    scorecard = row.get("research_scorecard") or {}
    overlay = row.get("overlay") or {}
    execution_gate = row.get("execution_gate") or {}
    symbol = row.get("ticker") or cluster.get("primary_ticker")
    return {
        "symbol": symbol,
        "company_name": cluster.get("company_name"),
        "catalyst_type": cluster.get("catalyst_type_primary"),
        "claim_summary": cluster.get("claim_summary"),
        "research_priority_score": row.get("research_priority_score"),
        "catalyst_strength_score": scorecard.get("catalyst_strength_score"),
        "freshness_score": scorecard.get("freshness_score"),
        "attention_acceleration_score": scorecard.get("attention_acceleration_score"),
        "crowding_score": scorecard.get("crowding_score"),
        "story_stage": row.get("story_stage") or scorecard.get("story_stage"),
        "official_confirmation_count": scorecard.get("official_confirmation_count"),
        "structured_confirmation_count": scorecard.get("structured_confirmation_count"),
        "social_confirmation_count": scorecard.get("social_confirmation_count"),
        "validation_status": scorecard.get("validation_status"),
        "hyper_trade_score": row.get("hyper_trade_score") or scorecard.get("hyper_trade_score"),
        "lane_tags": row.get("lane_tags") or scorecard.get("lane_tags") or [],
        "last_price": overlay.get("last_premarket_price"),
        "gap_pct": overlay.get("gap_pct"),
        "premarket_volume": overlay.get("premarket_volume"),
        "premarket_dollar_volume": overlay.get("premarket_dollar_volume"),
        "spread_pct": overlay.get("estimated_spread_pct"),
        "execution_gate_pass": execution_gate.get("passed", False),
        "execution_readiness_score": execution_gate.get("execution_readiness_score", overlay.get("execution_readiness_score")),
        "execution_blockers": execution_gate.get("blockers", overlay.get("execution_blockers", [])),
        "execution_warnings": execution_gate.get("warnings", overlay.get("execution_warnings", [])),
        "anti_chase_state": overlay.get("anti_chase_state"),
        "opportunity_lifecycle_state": overlay.get("opportunity_lifecycle_state"),
        "entry_viability_score": overlay.get("entry_viability_score"),
    }


def _execution_state(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"anti_chase_state": None, "opportunity_lifecycle_state": None, "entry_viability_score": None}
    try:
        gap = abs(float(row.get("gap_pct") or 0.0))
    except Exception:
        gap = 0.0
    try:
        spread_pct = float(row.get("spread_pct") or 0.0)
    except Exception:
        spread_pct = 0.0
    lanes = set(row.get("lane_tags") or [])
    catalyst_validated = bool(lanes.intersection({"POLICY_THEME_RUNNER_ARCHETYPE", "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE", "VERIFIED_CATALYST_RUNNER"})) or bool(row.get("official_confirmation_count") or row.get("structured_confirmation_count"))
    state = classify_anti_chase_state(
        gap_pct=gap,
        estimated_spread_pct=spread_pct,
        premarket_dollar_volume=row.get("premarket_dollar_volume"),
        execution_blockers=row.get("execution_blockers") or [],
        catalyst_validated=catalyst_validated,
    )
    if row.get("execution_blockers"):
        state["opportunity_lifecycle_state"] = lc.SECOND_LEG_WATCH if state["anti_chase_state"] in {lc.SECOND_LEG_WATCH, lc.EXTENDED_CHASE} else lc.EXHAUSTED_OR_DISTRIBUTING
    return state


def _same_style_backup_status(research_rows: list[dict[str, Any]], leader_symbol: str | None) -> dict[str, Any]:
    leader = str(leader_symbol or "").upper()
    same_style: list[str] = []
    megacaps: list[str] = []
    considered: list[dict[str, Any]] = []
    for raw in research_rows:
        row = _render_watch_row(raw)
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol == leader:
            continue
        lanes = set(row.get("lane_tags") or [])
        reasons: list[str] = []
        if lanes.intersection({"POLICY_THEME_RUNNER_ARCHETYPE", "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE"}):
            reasons.append("policy_theme_or_same_theme")
        if float(row.get("hyper_trade_score") or 0.0) >= 2.0:
            reasons.append("high_hyper_trade_score")
        if abs(float(row.get("gap_pct") or 0.0)) >= 5.0:
            reasons.append("top_premarket_gapper")
        if float(row.get("premarket_dollar_volume") or 0.0) >= 1_000_000:
            reasons.append("high_premarket_dollar_volume")
        if float(row.get("attention_acceleration_score") or 0.0) >= 5.0 or int(row.get("social_confirmation_count") or 0) > 0:
            reasons.append("retail_attention_or_social_confirmation")
        if row.get("catalyst_type"):
            reasons.append("fresh_catalyst_name")
        is_same_style = symbol not in MEGACAP_DEFAULT_TICKERS and (
            lanes.intersection({"POLICY_THEME_RUNNER_ARCHETYPE", "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE"})
            or float(row.get("hyper_trade_score") or 0.0) >= 2.0
            or abs(float(row.get("gap_pct") or 0.0)) >= 5.0
        )
        considered.append(
            {
                "symbol": symbol,
                "selected": bool(is_same_style),
                "mega_cap": symbol in MEGACAP_DEFAULT_TICKERS,
                "reasons": reasons,
                "lane_tags": sorted(lanes),
                "gap_pct": row.get("gap_pct"),
                "hyper_trade_score": row.get("hyper_trade_score"),
                "premarket_dollar_volume": row.get("premarket_dollar_volume"),
                "catalyst_type": row.get("catalyst_type"),
            }
        )
        if is_same_style:
            same_style.append(symbol)
        elif symbol in MEGACAP_DEFAULT_TICKERS:
            megacaps.append(symbol)
    failures = [] if len(same_style) >= 3 else ["same_style_backup_pool_below_minimum"]
    return {
        "leader": leader or None,
        "same_style_non_megacap_backups": same_style[:8],
        "megacap_default_backups": megacaps[:8],
        "same_style_backup_pool_ok": len(same_style) >= 3,
        "reason": None if len(same_style) >= 3 else "same_style_backup_pool_failed",
        "backup_pool_diagnostics": {
            "same_style_candidates_considered": considered[:20],
            "same_style_candidates_selected": same_style[:8],
            "mega_cap_backups_used": megacaps[:8] if len(same_style) < 3 else [],
            "reason_mega_cap_backup_used": "same_style_backup_pool_failed" if len(same_style) < 3 and megacaps else None,
            "source_lane_failures_affecting_backups": failures,
        },
    }


def _candidate_roles(research_ranked: list[dict[str, Any]], rendered_watchlist: dict[str, list[dict[str, Any]]], execution_watchlist: list[dict[str, Any]], packet: dict[str, Any]) -> dict[str, Any]:
    rendered_ranked = [_render_watch_row(row) for row in research_ranked]
    leader_symbol = packet.get("research_leader") or packet.get("best_pick") or (rendered_ranked[0].get("symbol") if rendered_ranked else None)
    leader_row = _find_rendered_row(leader_symbol, rendered_watchlist, research_ranked, execution_watchlist)
    leader_state = _execution_state(leader_row)
    executable_primary = None
    if (
        leader_row
        and leader_row.get("execution_gate_pass")
        and leader_state.get("anti_chase_state") == lc.PREMARKET_BUILDING
        and float(leader_state.get("entry_viability_score") or 0.0) >= 60.0
    ):
        executable_primary = {**leader_row, **leader_state}
    watch_only: list[dict[str, Any]] = []
    second_leg_watch: list[dict[str, Any]] = []
    no_trade_extended: list[dict[str, Any]] = []
    for row in rendered_ranked[:15]:
        state = _execution_state(row)
        enriched = {**row, **state}
        if state.get("anti_chase_state") in {lc.SECOND_LEG_WATCH, lc.EXTENDED_CHASE}:
            second_leg_watch.append(enriched)
        elif state.get("anti_chase_state") == lc.NO_TRADE_EXTENDED:
            no_trade_extended.append(enriched)
        elif row.get("execution_blockers"):
            watch_only.append(enriched)
    return {
        "research_leader": {**leader_row, **leader_state} if leader_row else None,
        "research_leader_symbol": leader_symbol,
        "executable_primary": executable_primary,
        "watch_only": watch_only,
        "second_leg_watch": second_leg_watch,
        "no_trade_extended": no_trade_extended,
        "anti_chase_state": leader_state.get("anti_chase_state"),
        "opportunity_lifecycle_state": leader_state.get("opportunity_lifecycle_state"),
        "entry_viability_score": leader_state.get("entry_viability_score"),
    }


def _find_rendered_row(symbol: str | None, rendered_watchlist: dict[str, list[dict[str, Any]]], research_ranked: list[dict[str, Any]], execution_watchlist: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not symbol:
        return None
    upper = str(symbol).upper()
    for rows in rendered_watchlist.values():
        for row in rows:
            if str(row.get("symbol") or "").upper() == upper:
                return row
    for row in execution_watchlist:
        rendered = _render_watch_row(row)
        if str(rendered.get("symbol") or "").upper() == upper:
            return rendered
    for row in research_ranked:
        rendered = _render_watch_row(row)
        if str(rendered.get("symbol") or "").upper() == upper:
            return rendered
    return None


def _stringify_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _parse_timestamp(value: Any) -> datetime | None:
    normalized = _stringify_timestamp(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except Exception:
        return None


def _market_session_snapshot(cfg: dict[str, Any]) -> dict[str, Any]:
    # Market-session timing is exchange-level state, not execution-broker state.
    # Alpaca is still the configured clock source even when live orders route
    # through Webull.
    snapshot = AlpacaClockAdapter().get_clock()
    if not snapshot.get("ok"):
        return snapshot
    clock = snapshot.get("clock") or {}
    timestamp = _parse_timestamp(clock.get("timestamp"))
    next_open = _parse_timestamp(clock.get("next_open"))
    is_open = bool(clock.get("is_open"))
    same_day_session_ahead = bool(timestamp and next_open and timestamp.date() == next_open.date())
    return {
        "ok": True,
        "timestamp": _stringify_timestamp(clock.get("timestamp")),
        "is_open": is_open,
        "next_open": _stringify_timestamp(clock.get("next_open")),
        "next_close": _stringify_timestamp(clock.get("next_close")),
        "same_day_session_ahead": same_day_session_ahead,
        "market_closed_for_day": (not is_open) and (not same_day_session_ahead),
    }


def build_premarket_report() -> dict[str, Any]:
    cfg = load_live_config()
    workflow_cfg = load_workflow_config()
    watch_cfg = ((workflow_cfg.get("workflow") or {}).get("watchlist") or {})
    storage = _today_storage()
    market_session = _market_session_snapshot(cfg)

    if market_session.get("ok") and market_session.get("market_closed_for_day"):
        next_open = market_session.get("next_open")
        source_lane_status = _load_json_if_exists(storage, "normalized/source_lane_status.json", build_source_lane_status([]))
        same_style_backups = {
            "leader": None,
            "same_style_non_megacap_backups": [],
            "megacap_default_backups": [],
            "same_style_backup_pool_ok": False,
            "reason": "market_closed_for_day",
            "backup_pool_diagnostics": {
                "same_style_candidates_considered": [],
                "same_style_candidates_selected": [],
                "mega_cap_backups_used": [],
                "reason_mega_cap_backup_used": None,
                "source_lane_failures_affecting_backups": ["market_closed_for_day"],
            },
        }
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "trading_date": storage.trading_day,
            "status": "market_closed",
            "market_session": market_session,
            "source_lane_status_path": str(storage.path("normalized/source_lane_status.json")),
            "symbols_considered": [],
            "sources": {
                "market_clock": {"ok": True, "count": 1, "reason": f"market_closed_until:{next_open}" if next_open else "market_closed_for_day"},
                "research_manifest": {"ok": False, "count": 0, "reason": "skipped_market_closed_for_day"},
                "dynamic_discovery": {"ok": False, "count": 0, "reason": "skipped_market_closed_for_day"},
                "execution_overlays": {"ok": False, "count": 0, "reason": "skipped_market_closed_for_day"},
                "overlay_cache": {"ok": False, "count": 0, "reason": "skipped_market_closed_for_day"},
                "deep_mini_governed": {"ok": False, "count": 0, "reason": "skipped_market_closed_for_day"},
                "best_pick_packet": {"ok": False, "count": 0, "reason": "skipped_market_closed_for_day"},
            },
            "watchlist": {"A": [], "B": [], "C": []},
            "research_ranked": [],
            "execution_watchlist": [],
            "best_pick_candidate": None,
            "research_leader": None,
            "executable_primary": None,
            "watch_only": [],
            "second_leg_watch": [],
            "no_trade_extended": [],
            "anti_chase_state": None,
            "opportunity_lifecycle_state": lc.NO_TRADE_EXTENDED,
            "entry_viability_score": 0.0,
            "same_style_backup_status": same_style_backups,
            "backup_pool_diagnostics": same_style_backups["backup_pool_diagnostics"],
            "source_lane_status": source_lane_status,
            "raw_candidate_count": 0,
            "top_raw_candidates": [],
            "first_seen_candidates": [],
            "broad_ai_discovery_candidates": [],
            "enriched_candidate_count": 0,
            "deep_research_route": None,
            "deep_research_status": "not_run",
            "current_action": "NO_TRADE_MARKET_CLOSED",
            "buy_now_allowed": False,
            "why_not_buy_now": "Market closed for day.",
            "buy_triggers": [],
            "monitoring_plan_through_11_et": False,
            "best_pick_packet": {},
            "candidate_research_packets": [],
            "no_trade_list": [
                {"symbol": "MARKET", "reason": f"U.S. equities market closed for the day; next open {next_open}" if next_open else "U.S. equities market closed for the day"}
            ],
        }

    manifest = _load_json_if_exists(storage, "meta/run_manifest.json", None)
    if not manifest:
        manifest = ResearchPipeline(cfg, workflow_cfg).run_once(manual_symbols=_manual_symbol_overrides())

    discovered_symbols = _load_json_if_exists(storage, "normalized/discovered_symbols.json", [])
    research_ranked = _load_json_if_exists(storage, "normalized/research_ranked_candidates.json", [])
    execution_watchlist = _load_json_if_exists(storage, "normalized/execution_eligible_candidates.json", [])
    execution_blocked = _load_json_if_exists(storage, "normalized/execution_blocked_candidates.json", [])
    daily_best_pick_packet = _load_json_if_exists(storage, "normalized/daily_best_pick_packet.json", {})
    candidate_research_packets = _load_json_if_exists(storage, "normalized/candidate_research_packets.json", [])

    top_symbols = [row.get("ticker") for row in (execution_watchlist or research_ranked)[: max(8, int((watch_cfg.get("tier_count") or {}).get("C", 8))) ] if row.get("ticker")]
    cached_overlays = _load_json_if_exists(storage, "overlays/market_overlay.json", {})
    cached_overlays = cached_overlays if isinstance(cached_overlays, dict) else {}
    overlays_dict = {ticker: payload for ticker, payload in cached_overlays.items() if ticker in top_symbols and _overlay_dict_is_fresh(payload)}
    cache_hits = len(overlays_dict)
    missing_symbols = [symbol for symbol in top_symbols if symbol not in overlays_dict]
    fresh_overlays = build_market_overlays(missing_symbols, cfg=cfg) if missing_symbols else {}
    if fresh_overlays:
        overlays_dict.update({ticker: overlay.to_dict() for ticker, overlay in fresh_overlays.items()})
        storage.write_json("overlays/market_overlay.json", {**cached_overlays, **overlays_dict})

    for row in research_ranked:
        ticker = row.get("ticker")
        if ticker and ticker in overlays_dict:
            row["overlay"] = overlays_dict[ticker]
    for row in execution_watchlist:
        ticker = row.get("ticker")
        if ticker and ticker in overlays_dict:
            row["overlay"] = overlays_dict[ticker]

    watchlist = _tier_watchlist(research_ranked, execution_watchlist, watch_cfg)
    rendered_watchlist = {tier: [_render_watch_row(row) for row in rows] for tier, rows in watchlist.items()}
    packet_best_symbol = (daily_best_pick_packet or {}).get("best_pick") if isinstance(daily_best_pick_packet, dict) else None
    packet_caveats = (daily_best_pick_packet or {}).get("caveats") if isinstance(daily_best_pick_packet, dict) else []
    deep_required = bool((daily_best_pick_packet or {}).get("deep_mini_required_for_live_research")) or deep_mini_required_for_live_research(
        ((workflow_cfg.get("workflow") or {}).get("deep_research") or {}),
        (cfg.get("research_mode") or {}),
    )
    deep_artifact_status = (daily_best_pick_packet or {}).get("deep_mini_artifact_status") or {}
    deep_completed = bool(deep_artifact_status.get("completed"))
    deep_required_blocked = deep_required and not deep_completed
    no_execution_pick = (not execution_watchlist) or ("no_execution_eligible_candidate" in (packet_caveats or [])) or deep_required_blocked
    best_pick = None if no_execution_pick else _find_rendered_row(packet_best_symbol, rendered_watchlist, research_ranked, execution_watchlist)
    if not best_pick and not no_execution_pick:
        best_pick = rendered_watchlist["A"][0] if rendered_watchlist["A"] else (_render_watch_row(research_ranked[0]) if research_ranked else None)
    if best_pick and best_pick.get("execution_blockers"):
        best_pick = None
    degraded = not rendered_watchlist["A"] or not best_pick

    deep_run = (((manifest or {}).get("artifacts") or {}).get("deep_mini_run") or {}) if isinstance(manifest, dict) else {}
    source_lane_status = _load_json_if_exists(storage, "normalized/source_lane_status.json", [])
    raw_candidates = _load_json_if_exists(storage, "raw/top_raw_candidates.json", [])
    first_seen_candidates = _load_json_if_exists(storage, "normalized/first_seen_candidates.json", [])
    broad_ai_candidates = _load_json_if_exists(storage, "raw/broad_ai_discovery_candidates.json", [])
    roles = _candidate_roles(research_ranked, rendered_watchlist, execution_watchlist, daily_best_pick_packet if isinstance(daily_best_pick_packet, dict) else {})
    if deep_required_blocked:
        roles["executable_primary"] = None
    same_style_backups = _same_style_backup_status(research_ranked, roles.get("research_leader_symbol"))
    authorization = authorize_one_ticker_trade(
        daily_best_pick_packet if isinstance(daily_best_pick_packet, dict) else {},
        deep_mini_required=deep_required,
        deep_mini_completed=deep_completed,
        same_style_backup_pool_ok=bool(same_style_backups.get("same_style_backup_pool_ok")),
        executable_primary=roles.get("executable_primary"),
    )
    enforce_authorization = deep_required or bool((daily_best_pick_packet or {}).get("trade_authorization"))
    if enforce_authorization and not authorization.authorized:
        best_pick = None
        roles["executable_primary"] = None
    authorization_payload = authorization.to_dict()
    trade_ticket = load_today_ticket(repo_root(), storage.trading_day)
    if trade_ticket is None and isinstance(daily_best_pick_packet, dict):
        trade_ticket = ticket_from_final_packet(
            daily_best_pick_packet,
            trading_date=storage.trading_day,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            completed_before_deadline=deep_completed,
            same_style_backup_pool_ok=bool(same_style_backups.get("same_style_backup_pool_ok")),
        )
        ticket_validation_for_write = validate_ticket(trade_ticket)
        trade_ticket["valid"] = ticket_validation_for_write.valid
        trade_ticket["blockers"] = ticket_validation_for_write.blockers
        storage.write_json("trade_authorization_ticket.json", trade_ticket)
    ticket_validation = validate_ticket(trade_ticket)
    if isinstance(daily_best_pick_packet, dict):
        daily_best_pick_packet = {
            **daily_best_pick_packet,
            "trade_authorization": authorization_payload,
            "executable_primary": authorization.ticker if authorization.authorized else None,
            "buy_now_allowed": authorization.authorized,
            "deterministic_fallback_executable_allowed": False,
        }
    buy_now_allowed = (authorization.authorized if enforce_authorization else True) and bool(roles.get("executable_primary"))
    why_not_buy_now = None if buy_now_allowed else (
        DEEP_MINI_REQUIRED_BLOCKER
        if deep_required_blocked
        else "; ".join(authorization.blockers or ["No executable_primary: current leader requires validated tape/entry-quality gates before buy_now."])
    )
    report_status = "NO_TRADE_RESEARCH_INCOMPLETE" if (deep_required_blocked or (enforce_authorization and not authorization.authorized)) else ("degraded" if degraded else "ok")
    current_action = "BUY_NOW_ALLOWED" if buy_now_allowed else ("NO_TRADE_RESEARCH_INCOMPLETE" if report_status == "NO_TRADE_RESEARCH_INCOMPLETE" else "WATCH_OR_NO_TRADE")

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trading_date": storage.trading_day,
        "status": report_status,
        "market_session": market_session,
        "source_lane_status_path": str(storage.path("normalized/source_lane_status.json")),
        "symbols_considered": discovered_symbols,
        "sources": {
            "market_clock": {"ok": bool(market_session.get("ok")), "count": 1 if market_session.get("ok") else 0, "reason": market_session.get("reason")},
            "research_manifest": {"ok": bool(manifest), "mode": (manifest or {}).get("mode"), "generated_at_utc": (manifest or {}).get("generated_at_utc")},
            "dynamic_discovery": {"ok": bool(discovered_symbols), "count": len(discovered_symbols), "reason": None if discovered_symbols else "no_discovered_symbols"},
            "execution_overlays": {"ok": bool(overlays_dict), "count": len(overlays_dict), "reason": None if overlays_dict else "overlay_data_unavailable"},
            "overlay_cache": {"ok": bool(cache_hits), "count": cache_hits, "reason": None if cache_hits else (None if cached_overlays else "overlay_cache_empty")},
            "deep_mini_governed": {"ok": bool(deep_run.get("success")), "count": 1 if deep_run else 0, "reason": deep_run.get("error") or (None if deep_run else "deep_mini_not_run")},
            "best_pick_packet": {"ok": bool(daily_best_pick_packet), "count": 1 if daily_best_pick_packet else 0, "reason": None if daily_best_pick_packet else "best_pick_packet_missing"},
            "candidate_research_packets": {"ok": bool(candidate_research_packets), "count": len(candidate_research_packets), "reason": None if candidate_research_packets else "candidate_packets_missing"},
        },
        "deep_mini_required_for_live_research": deep_required,
        "deep_mini_broad_status": deep_artifact_status.get("broad_status"),
        "deep_mini_shortlist_status": deep_artifact_status.get("shortlist_status"),
        "deep_mini_red_team_status": deep_artifact_status.get("red_team_status"),
        "deep_mini_request_ids": [],
        "deep_mini_artifact_paths": deep_artifact_status.get("paths") or {},
        "deep_mini_completed_before_deadline": deep_completed,
        "deterministic_fallback_used": (daily_best_pick_packet or {}).get("source_mode") == "internal_fallback",
        "deterministic_fallback_executable_allowed": False,
        "trade_authorization_ticket_path": str(storage.path("trade_authorization_ticket.json")),
        "trade_authorization_ticket_valid": ticket_validation.valid,
        "trade_authorization_ticket_blockers": ticket_validation.blockers,
        "trade_authorization": authorization_payload,
        "one_ticker_trade_authorization_required": True,
        "watchlist": rendered_watchlist,
        "research_ranked": [_render_watch_row(row) for row in research_ranked[:15]],
        "execution_watchlist": [_render_watch_row(row) for row in execution_watchlist[:10]],
        "best_pick_candidate": best_pick,
        "research_leader": roles.get("research_leader"),
        "executable_primary": roles.get("executable_primary"),
        "watch_only": roles.get("watch_only"),
        "second_leg_watch": roles.get("second_leg_watch"),
        "no_trade_extended": roles.get("no_trade_extended"),
        "anti_chase_state": roles.get("anti_chase_state"),
        "opportunity_lifecycle_state": roles.get("opportunity_lifecycle_state"),
        "entry_viability_score": roles.get("entry_viability_score"),
        "same_style_backup_status": same_style_backups,
        "backup_pool_diagnostics": same_style_backups.get("backup_pool_diagnostics"),
        "source_lane_status": source_lane_status,
        "raw_candidate_count": len(raw_candidates),
        "top_raw_candidates": raw_candidates[:25],
        "first_seen_candidates": first_seen_candidates,
        "broad_ai_discovery_candidates": broad_ai_candidates,
        "enriched_candidate_count": len(candidate_research_packets) if isinstance(candidate_research_packets, list) else 0,
        "deep_research_route": deep_run.get("route_chosen") if isinstance(deep_run, dict) else None,
        "deep_research_status": deep_run.get("status") if isinstance(deep_run, dict) else "not_run",
        "current_action": current_action,
        "buy_now_allowed": buy_now_allowed,
        "why_not_buy_now": why_not_buy_now,
        "buy_triggers": [
            "VWAP reclaim on expanding volume",
            "ORB break above local high",
            "Premarket-high reclaim with spread stable",
        ],
        "monitoring_plan_through_11_et": True,
        "best_pick_packet": daily_best_pick_packet,
        "candidate_research_packets": candidate_research_packets[:10] if isinstance(candidate_research_packets, list) else [],
        "no_trade_list": [
            {"symbol": row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker")), "reason": "; ".join((row.get("execution_gate") or {}).get("blockers") or ["blocked"])}
            for row in execution_blocked[:20]
        ],
    }


def write_report(report: dict[str, Any], root: Path) -> tuple[Path, Path]:
    trading_day = str(report.get("trading_date") or os.getenv("ROI_SNIPS_TRADE_DATE", "").strip() or datetime.now().strftime("%Y-%m-%d"))
    json_dir = root / "reports" / "morning" / "json"
    md_dir = root / "reports" / "morning" / "md"
    json_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    suffix = os.getenv("ROI_SNIPS_REPORT_SUFFIX", "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = f"_{suffix}"
    json_path = json_dir / f"{trading_day}{suffix}.json"
    md_path = md_dir / f"{trading_day}{suffix}.md"
    json_path.write_text(json.dumps(report, indent=2))

    lines = ["# Roi Snips Morning Report", "", f"Generated: {report['generated_at_utc']}", f"Status: {report['status']}", ""]
    market_session = report.get("market_session") or {}
    lines.append("## Market session")
    if market_session:
        lines.append(f"- is_open={market_session.get('is_open')} same_day_session_ahead={market_session.get('same_day_session_ahead')} next_open={market_session.get('next_open')}")
    else:
        lines.append("- unavailable")
    lines.append("")
    best = report.get("best_pick_candidate")
    lines.append("## Best pick candidate")
    if not best:
        lines.append("- none")
    else:
        lines.extend(
            [
                f"- {best['symbol']} | research_priority={best.get('research_priority_score')} | catalyst={best.get('catalyst_type')} | story_stage={best.get('story_stage')}",
                f"  - catalyst_strength={best.get('catalyst_strength_score')} freshness={best.get('freshness_score')} attention={best.get('attention_acceleration_score')} crowding={best.get('crowding_score')} validation={best.get('validation_status')}",
                f"  - hyper_trade_score={best.get('hyper_trade_score')} lanes={', '.join(best.get('lane_tags') or []) or 'none'}",
                f"  - last_price={best.get('last_price')} gap_pct={best.get('gap_pct')} premarket_volume={best.get('premarket_volume')} spread_pct={best.get('spread_pct')}",
                f"  - execution_gate_pass={best.get('execution_gate_pass')} execution_readiness_score={best.get('execution_readiness_score')}",
                f"  - execution_blockers={', '.join(best.get('execution_blockers') or []) or 'none'}",
                f"  - claim_summary={best.get('claim_summary')}",
            ]
        )
    lines.append("")
    lines.append("## Candidate roles")
    leader = report.get("research_leader") or {}
    executable = report.get("executable_primary") or {}
    lines.append(f"- research_leader={leader.get('symbol') if leader else None} anti_chase_state={report.get('anti_chase_state')} lifecycle={report.get('opportunity_lifecycle_state')} entry_viability={report.get('entry_viability_score')}")
    lines.append(f"- executable_primary={executable.get('symbol') if executable else None}")
    second_leg = report.get("second_leg_watch") or []
    if second_leg:
        lines.append("- second_leg_watch:")
        for row in second_leg[:5]:
            lines.append(f"  - {row.get('symbol')} anti_chase_state={row.get('anti_chase_state')} gap_pct={row.get('gap_pct')} hyper={row.get('hyper_trade_score')}")
    else:
        lines.append("- second_leg_watch: none")
    backup_status = report.get("same_style_backup_status") or {}
    lines.append(f"- same_style_backup_pool_ok={backup_status.get('same_style_backup_pool_ok')} reason={backup_status.get('reason')}")
    if backup_status.get("same_style_non_megacap_backups"):
        lines.append(f"- same_style_non_megacap_backups={', '.join(backup_status.get('same_style_non_megacap_backups') or [])}")
    if backup_status.get("megacap_default_backups"):
        lines.append(f"- megacap_default_backups={', '.join(backup_status.get('megacap_default_backups') or [])}")
    diagnostics = report.get("backup_pool_diagnostics") or backup_status.get("backup_pool_diagnostics") or {}
    if diagnostics:
        lines.append("- backup_pool_diagnostics:")
        lines.append(f"  - same_style_candidates_selected={', '.join(diagnostics.get('same_style_candidates_selected') or []) or 'none'}")
        lines.append(f"  - mega_cap_backups_used={', '.join(diagnostics.get('mega_cap_backups_used') or []) or 'none'}")
        lines.append(f"  - reason_mega_cap_backup_used={diagnostics.get('reason_mega_cap_backup_used')}")
        lines.append(f"  - source_lane_failures_affecting_backups={', '.join(diagnostics.get('source_lane_failures_affecting_backups') or []) or 'none'}")
    lines.append("")

    packet = report.get("best_pick_packet") or {}
    if packet:
        lines.append("## Governed best-pick memo")
        lines.append(f"- source_mode={packet.get('source_mode')} route={packet.get('route_chosen')} best_pick={packet.get('best_pick')}")
        if packet.get("executive_summary"):
            lines.append(f"- executive_summary={packet.get('executive_summary')}")
        if packet.get("why_best_pick_wins"):
            lines.append(f"- why_best_pick_wins={packet.get('why_best_pick_wins')}")
        if packet.get("research_leader"):
            lines.append(f"- research_leader={packet.get('research_leader')}")
        if packet.get("why_market_may_not_be_fully_priced"):
            lines.append(f"- why_market_may_not_be_fully_priced={packet.get('why_market_may_not_be_fully_priced')}")
        if packet.get("suggested_buy_zone"):
            lines.append(f"- suggested_buy_zone={packet.get('suggested_buy_zone')}")
        if packet.get("same_day_upside_target"):
            lines.append(f"- same_day_upside_target={packet.get('same_day_upside_target')}")
        if packet.get("one_to_three_day_upside_target"):
            lines.append(f"- one_to_three_day_upside_target={packet.get('one_to_three_day_upside_target')}")
        if packet.get("thesis_break_level"):
            lines.append(f"- thesis_break_level={packet.get('thesis_break_level')}")
        backups = packet.get("ranked_backups") or []
        if backups:
            lines.append("- ranked_backups:")
            for row in backups:
                lines.append(f"  - {row.get('ticker')}: {row.get('summary')}")
        risks = packet.get("key_invalidation_risks") or []
        if risks:
            lines.append("- invalidation_risks:")
            for risk in risks:
                lines.append(f"  - {risk}")
        for label, key in [
            ("monitoring_timeframes", "monitoring_timeframes"),
            ("profit_taking_triggers", "profit_taking_triggers"),
            ("danger_signals", "danger_signals"),
        ]:
            values = packet.get(key) or []
            if values:
                lines.append(f"- {label}:")
                for value in values:
                    lines.append(f"  - {value}")
        caveats = packet.get("caveats") or []
        if caveats:
            lines.append("- caveats:")
            for caveat in caveats:
                lines.append(f"  - {caveat}")
        lines.append("")

    candidate_packets = report.get("candidate_research_packets") or []
    if candidate_packets:
        lines.append("## Candidate research packets")
        for packet in candidate_packets[:5]:
            scorecard = packet.get("scorecard") or {}
            market = packet.get("market_snapshot") or {}
            gate = packet.get("deterministic_trade_gate_status") or {}
            lines.extend(
                [
                    f"- {packet.get('ticker')} | validation={packet.get('validation_status')} | confidence={packet.get('source_confidence')} | hyper={scorecard.get('hyper_trade_score')}",
                    f"  - thesis={packet.get('headline_thesis')}",
                    f"  - market gap={market.get('gap_pct')} premarket_dollar_volume={market.get('premarket_dollar_volume')} spread={market.get('estimated_spread_pct')}",
                    f"  - why_asymmetric={'; '.join(packet.get('why_asymmetric') or [])}",
                    f"  - why_wrong={'; '.join(packet.get('why_it_may_be_wrong') or [])}",
                    f"  - trade_gate_pass={gate.get('passed')} blockers={', '.join(gate.get('blockers') or []) or 'none'}",
                ]
            )
        lines.append("")

    for tier in ["A", "B", "C"]:
        lines.append(f"## {tier}-tier")
        rows = (report.get("watchlist") or {}).get(tier) or []
        if not rows:
            lines.append("- none")
        else:
            for row in rows:
                lines.extend(
                    [
                        f"- {row['symbol']} | research_priority={row.get('research_priority_score')} | hyper={row.get('hyper_trade_score')} | catalyst={row.get('catalyst_type')} | story_stage={row.get('story_stage')} | validation={row.get('validation_status')}",
                        f"  - execution_gate_pass={row.get('execution_gate_pass')} blockers={', '.join(row.get('execution_blockers') or []) or 'none'}",
                        f"  - claim_summary={row.get('claim_summary')}",
                    ]
                )
        lines.append("")

    lines += ["## No-trade list"]
    if report["no_trade_list"]:
        for row in report["no_trade_list"][:30]:
            lines.append(f"- {row.get('symbol')}: {row.get('reason')}")
    else:
        lines.append("- none")

    lines += ["", "## Source status"]
    for key, value in report["sources"].items():
        lines.append(f"- {key}: ok={value.get('ok')} count={value.get('count')} reason={value.get('reason')}")
    lane_status = report.get("source_lane_status") or []
    if lane_status:
        lines.append("")
        lines.append("## Source lane status")
        for row in lane_status:
            lines.append(
                f"- {row.get('lane_name')}: configured={row.get('configured')} ran={row.get('ran')} produced_candidates={row.get('produced_candidates_count', row.get('produced_candidates'))} useful_evidence={row.get('produced_useful_evidence_count')} useful_for_primary={row.get('affected_primary_selection', row.get('useful_for_primary'))} affected_backup_list={row.get('affected_backup_list')} missing_credentials={','.join(row.get('missing_credentials') or []) or 'none'} errors={'; '.join(row.get('errors') or []) or 'none'}"
            )

    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


if __name__ == "__main__":
    root = repo_root()
    report = build_premarket_report()
    json_path, md_path = write_report(report, root)
    print(json.dumps({"ok": True, "status": report.get("status"), "json": str(json_path), "md": str(md_path)}))
