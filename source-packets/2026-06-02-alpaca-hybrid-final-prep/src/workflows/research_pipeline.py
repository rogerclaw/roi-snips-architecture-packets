from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from ..common.config import load_live_config, load_workflow_config
from ..research.cluster import cluster_events, select_claim_summary_for_ticker
from ..research.candidate_packets import build_candidate_research_packets
from ..research.gates import apply_execution_gate
from ..research.first_seen import FIRST_SEEN_PATH, load_first_seen, merge_first_seen_records
from ..research.market_overlay import build_market_overlays
from ..research.metrics import summarize_run
from ..research.raw_discovery import build_raw_runner_candidates, summarize_raw_discovery
from ..research.ranking import rank_clusters_for_research
from ..research.source_lane_status import build_source_lane_status
from ..research.trade_authorization_ticket import ticket_from_final_packet, validate_ticket
from ..research.scouts.exchange_scout import ExchangeScout
from ..research.scouts.external_source_scouts import ExternalMoversScout, FederalCatalystScout
from ..research.scouts.fda_scout import FdaScout
from ..research.scouts.government_scout import GovernmentScout
from ..research.scouts.ir_scout import IRScout
from ..research.scouts.newswire_scout import NewswireScout
from ..research.scouts.obscure_scout import ObscureScout
from ..research.scouts.sec_scout import SecScout
from ..research.scouts.social_scout import SocialScout
from ..research.scouts.theme_basket_scout import ThemeBasketScout
from ..research.storage import ResearchRunStorage
from ..research.universe import derive_candidate_universe
from .broad_ai_discovery import build_broad_ai_candidates, build_broad_ai_discovery_prompt
from .deep_mini_bridge import (
    DEEP_MINI_REQUIRED_BLOCKER,
    build_deep_mini_required_no_trade_packet,
    build_fallback_best_pick_packet,
    deep_mini_required_for_live_research,
    load_grok_social_context,
    run_governed_deep_mini,
    write_deep_mini_input,
    write_required_deep_mini_artifacts,
)
from .grok_d_research_bridge import (
    GROK_REQUIRED_BLOCKER,
    grok_required_for_live_research,
    run_governed_grok_d_research,
)


def _manual_symbol_overrides() -> list[str]:
    env = os.getenv("ROI_SNIPS_SYMBOLS", "")
    if not env.strip():
        return []
    return [s.strip().upper() for s in env.split(",") if s.strip()]


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _parse_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError(f"invalid_{name}:must_be_positive_integer") from exc
    if parsed <= 0:
        raise ValueError(f"invalid_{name}:must_be_positive_integer")
    return parsed


def _event_identity(event: dict[str, Any]) -> str:
    source_url = str(event.get("source_url") or "").strip()
    if source_url:
        return f"url:{source_url}"
    return "|".join(
        [
            str(event.get("source_name") or "").strip(),
            str(event.get("headline") or "").strip(),
            str(event.get("published_at") or event.get("discovered_at") or "").strip(),
        ]
    )


def _merge_ranked_by_ticker(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).upper()
        if not ticker:
            continue
        current = merged.get(ticker)
        if current is None:
            merged[ticker] = row
            continue
        current_cluster = current.get("cluster") or {}
        row_cluster = row.get("cluster") or {}
        current_events = list(current_cluster.get("events") or [])
        current_event_keys = {_event_identity(event) for event in current_events}
        for event in row_cluster.get("events") or []:
            key = _event_identity(event)
            if key not in current_event_keys:
                current_events.append(event)
                current_event_keys.add(key)
        current_events.sort(key=lambda event: (str(event.get("published_at") or event.get("discovered_at") or ""), str(event.get("source_name") or ""), str(event.get("headline") or "")))
        current_cluster["events"] = current_events
        current_cluster["claim_summary"] = select_claim_summary_for_ticker(ticker, current_events)
        for key in ["first_seen_at", "latest_update_at"]:
            values = [v for v in [current_cluster.get(key), row_cluster.get(key)] if v]
            if values:
                current_cluster[key] = min(values) if key == "first_seen_at" else max(values)
        for key in ["official_sources", "structured_sources", "social_sources", "obscure_sources", "catalyst_types_all"]:
            current_cluster[key] = sorted({*(current_cluster.get(key) or []), *(row_cluster.get(key) or [])})
        current_cluster["official_confirmation_count"] = len(current_cluster.get("official_sources") or [])
        current_cluster["structured_confirmation_count"] = len(current_cluster.get("structured_sources") or [])
        current_cluster["social_confirmation_count"] = len(current_cluster.get("social_sources") or [])
        current_cluster["obscure_confirmation_count"] = len(current_cluster.get("obscure_sources") or [])
        current["cluster"] = current_cluster
        scorecard = current.get("research_scorecard") or {}
        row_scorecard = row.get("research_scorecard") or {}
        for score_key in [
            "catalyst_strength_score",
            "freshness_score",
            "attention_acceleration_score",
            "asymmetry_score",
            "hyper_trade_score",
        ]:
            values = [scorecard.get(score_key), row_scorecard.get(score_key)]
            numeric = [float(value) for value in values if isinstance(value, (int, float))]
            if numeric:
                scorecard[score_key] = max(numeric)
        crowding_values = [scorecard.get("crowding_score"), row_scorecard.get("crowding_score")]
        numeric_crowding = [float(value) for value in crowding_values if isinstance(value, (int, float))]
        if numeric_crowding:
            scorecard["crowding_score"] = max(numeric_crowding)
        scorecard["notes"] = sorted({*(scorecard.get("notes") or []), *(row_scorecard.get("notes") or [])})
        scorecard["official_confirmation_count"] = current_cluster["official_confirmation_count"]
        scorecard["structured_confirmation_count"] = current_cluster["structured_confirmation_count"]
        scorecard["social_confirmation_count"] = current_cluster["social_confirmation_count"]
        if current_cluster["official_confirmation_count"] and current_cluster["structured_confirmation_count"]:
            scorecard["validation_status"] = "primary_and_structured_confirmed"
        elif current_cluster["official_confirmation_count"]:
            scorecard["validation_status"] = "primary_confirmed"
        elif current_cluster["structured_confirmation_count"]:
            scorecard["validation_status"] = "structured_confirmed"
        elif current_cluster["social_confirmation_count"]:
            scorecard["validation_status"] = "social_discovery_only"
        current["research_scorecard"] = scorecard
        current["research_priority_score"] = max(float(current.get("research_priority_score") or 0.0), float(row.get("research_priority_score") or 0.0))
        current["hyper_trade_score"] = max(float(current.get("hyper_trade_score") or 0.0), float(row.get("hyper_trade_score") or 0.0))
        current["lane_tags"] = sorted({*(current.get("lane_tags") or []), *(row.get("lane_tags") or [])})
    out = list(merged.values())
    out.sort(
        key=lambda row: (
            row.get("hyper_trade_score") or 0,
            row.get("research_priority_score") or 0,
            (row.get("research_scorecard") or {}).get("catalyst_strength_score") or 0,
        ),
        reverse=True,
    )
    return out


class ResearchPipeline:
    def __init__(self, cfg: dict[str, Any] | None = None, workflow_cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or load_live_config()
        self.workflow_cfg = workflow_cfg or load_workflow_config()
        self.storage = ResearchRunStorage()
        self.discovery_scouts = [NewswireScout(), ExchangeScout(), ExternalMoversScout(), SocialScout(), ObscureScout(), IRScout(), FdaScout(), GovernmentScout(), ThemeBasketScout()]
        self.seeded_discovery_scouts = [SecScout()]
        self.evidence_scouts = [
            SecScout(),
            IRScout(),
            NewswireScout(),
            FdaScout(),
            ExchangeScout(),
            FederalCatalystScout(),
            GovernmentScout(),
            SocialScout(),
            ObscureScout(),
        ]

    def _thresholds(self) -> dict[str, Any]:
        workflow = self.workflow_cfg.get("workflow") or {}
        thresholds = workflow.get("thresholds") or {}
        if "research" in thresholds or "execution" in thresholds:
            return thresholds
        return {
            "research": {
                "max_candidates_after_discovery": thresholds.get("max_candidates_after_initial_filter", 40),
                "max_candidates_for_verification": thresholds.get("max_candidates_for_verification", 15),
                "max_candidates_for_deep_mini": thresholds.get("max_candidates_for_deep_mini", 5),
            },
            "execution": {
                "min_price": thresholds.get("min_price_aggressive", 3),
                "min_avg_dollar_volume": thresholds.get("min_avg_dollar_volume_aggressive", 10_000_000),
                "min_execution_readiness_score": float(thresholds.get("min_tradeability_score_for_best_pick", 6)) * 10.0,
            },
        }

    def _deep_research_cfg(self) -> dict[str, Any]:
        workflow = self.workflow_cfg.get("workflow") or {}
        cfg = dict(workflow.get("deep_research") or {"enabled": True, "mode": "deep_mini", "top_n_for_deep_mini": 3, "require_governed_route": True})
        research_mode = self.cfg.get("research_mode") or {}
        if research_mode.get("deep_mini_required_for_live_research") is True:
            cfg["require_for_live_research"] = True
        if research_mode.get("deterministic_fallback_executable_allowed") is False:
            cfg["allow_deterministic_fallback_for_live"] = False
        if "top_n_for_final_synthesis" in cfg and "top_n_for_deep_mini" not in cfg:
            cfg["top_n_for_deep_mini"] = cfg["top_n_for_final_synthesis"]
        if _env_truthy("ROI_SNIPS_SKIP_DEEP_MINI"):
            cfg["enabled"] = False
        if os.getenv("ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS", "").strip():
            cfg["timeout_seconds"] = _parse_positive_int(os.getenv("ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS", ""), "ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS")
        if os.getenv("ROI_SNIPS_DEEP_MINI_POLL_SECONDS", "").strip():
            cfg["poll_seconds"] = _parse_positive_int(os.getenv("ROI_SNIPS_DEEP_MINI_POLL_SECONDS", ""), "ROI_SNIPS_DEEP_MINI_POLL_SECONDS")
        if _env_truthy("ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH"):
            cfg["require_for_live_research"] = True
            cfg["allow_deterministic_fallback_for_live"] = False
        if _env_truthy("ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH"):
            cfg["grok_heat_layer_expected"] = True
            cfg["require_grok_for_live_research"] = False
            cfg["require_for_live_research"] = True
            cfg["allow_deterministic_fallback_for_live"] = False
        return cfg

    def _validate_deep_research_cfg(self, cfg: dict[str, Any]) -> list[str]:
        if not cfg.get("enabled", True):
            return []
        mode = str(cfg.get("mode") or "deep_mini").strip()
        if mode not in {"deep", "deep_mini"}:
            return [f"invalid_deep_research_mode:{mode}"]
        return []

    def _collect_from_scouts(self, scouts: list[Any], tickers: list[str] | None) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for scout in scouts:
            try:
                events.extend(scout.collect(tickers))
            except Exception as e:
                errors.append({"ts_utc": datetime.now(timezone.utc).isoformat(), "scout": scout.__class__.__name__, "error": str(e)})
        if errors:
            self.storage.write_jsonl("logs/errors.jsonl", errors, append=True)
        return events

    def collect_discovery_events(self, seed_symbols: list[str]) -> list[dict[str, Any]]:
        events = self._collect_from_scouts(self.discovery_scouts, seed_symbols or None)
        if seed_symbols:
            events.extend(self._collect_from_scouts(self.seeded_discovery_scouts, seed_symbols))
        return events

    def collect_evidence_events(self, candidate_symbols: list[str]) -> list[dict[str, Any]]:
        if not candidate_symbols:
            return []
        return self._collect_from_scouts(self.evidence_scouts, candidate_symbols)

    def run_once(
        self,
        max_candidates: int | None = None,
        manual_symbols: list[str] | None = None,
        discovery_only: bool = False,
        skip_overlays: bool = False,
        skip_deep_mini: bool = False,
    ) -> dict[str, Any]:
        thresholds = self._thresholds()
        research_cfg = thresholds.get("research") or {}
        manual = manual_symbols if manual_symbols is not None else _manual_symbol_overrides()

        discovery_events = self.collect_discovery_events(manual)
        self.storage.write_jsonl("raw/discovery_events.jsonl", discovery_events)
        raw_candidates = build_raw_runner_candidates(discovery_events, preserve_top_n=150)
        raw_discovery_summary = summarize_raw_discovery(raw_candidates)
        self.storage.write_json("raw/raw_runner_candidates.json", raw_candidates)
        self.storage.write_json("raw/top_raw_candidates.json", raw_candidates[:25])
        broad_candidates, broad_sources = build_broad_ai_candidates(
            raw_candidates,
            trading_date=self.storage.trading_day,
            failure_reason=None if raw_candidates else "no_raw_candidates_for_broad_discovery",
        )
        self.storage.write_json("raw/broad_ai_discovery_candidates.json", broad_candidates)
        self.storage.write_jsonl("raw/broad_ai_discovery_sources.jsonl", broad_sources)
        self.storage.write_json(
            "raw/broad_ai_discovery_prompt_contract.json",
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "prompt": build_broad_ai_discovery_prompt(self.storage.trading_day, broad_sources[:20]),
                "final_pick_allowed": False,
                "runs_before_strict_filtering": True,
            },
        )
        previous_first_seen = load_first_seen(self.storage.path(FIRST_SEEN_PATH))
        first_seen_records = merge_first_seen_records(
            previous_first_seen,
            raw_candidates,
            selected_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        self.storage.write_json(FIRST_SEEN_PATH, first_seen_records)

        candidate_symbols = derive_candidate_universe(
            discovery_events,
            include=manual,
            max_symbols=int(research_cfg.get("max_candidates_after_discovery", 40)),
        )
        self.storage.write_json("normalized/discovered_symbols.json", candidate_symbols)

        if discovery_only:
            manifest = {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "tickers": candidate_symbols,
                "summary": {
                    "discovery_events_count": len(discovery_events),
                    "discovered_symbols_count": len(candidate_symbols),
                    **raw_discovery_summary,
                    "broad_ai_discovery_candidate_count": len([row for row in broad_candidates if row.get("ticker")]),
                },
                "mode": "research_v2_discovery_only",
                "artifacts": {
                    "raw_runner_candidates": str(self.storage.path("raw/raw_runner_candidates.json")),
                    "top_raw_candidates": str(self.storage.path("raw/top_raw_candidates.json")),
                    "first_seen_candidates": str(self.storage.path(FIRST_SEEN_PATH)),
                    "broad_ai_discovery_candidates": str(self.storage.path("raw/broad_ai_discovery_candidates.json")),
                    "broad_ai_discovery_sources": str(self.storage.path("raw/broad_ai_discovery_sources.jsonl")),
                },
            }
            self.storage.write_json("meta/run_manifest.json", manifest)
            return manifest

        evidence_events = self.collect_evidence_events(candidate_symbols)
        all_events = [*discovery_events, *evidence_events]
        self.storage.write_jsonl("raw/all_events.jsonl", all_events)

        clusters = cluster_events(all_events)
        cluster_dicts = [cluster.to_dict() for cluster in clusters]
        self.storage.write_json("normalized/candidate_clusters.json", cluster_dicts)

        ranked_raw = rank_clusters_for_research(clusters)
        ranked = _merge_ranked_by_ticker(ranked_raw)
        self.storage.write_json("normalized/research_ranked_candidates.json", ranked)

        top_for_overlay = ranked[: int(max_candidates or research_cfg.get("max_candidates_for_verification", 15))]
        overlays = {}
        if not skip_overlays:
            overlays = build_market_overlays([row["ticker"] for row in top_for_overlay], cfg=self.cfg)
        self.storage.write_json("overlays/market_overlay.json", {ticker: overlay.to_dict() for ticker, overlay in overlays.items()})

        execution_gate_skipped = bool(skip_overlays)
        if execution_gate_skipped:
            execution_eligible = []
            execution_blocked = [
                {
                    **row,
                    "execution_gate": {
                        "passed": False,
                        "execution_readiness_score": None,
                        "blockers": ["market_overlay_skipped"],
                        "warnings": ["execution_gate_not_evaluated"],
                    },
                }
                for row in top_for_overlay
            ]
        else:
            execution_eligible, execution_blocked = apply_execution_gate(
                top_for_overlay,
                overlays,
                max_candidates=int(max_candidates or research_cfg.get("max_candidates_for_verification", 15)),
                cfg=thresholds,
            )
        self.storage.write_json("normalized/execution_eligible_candidates.json", execution_eligible)
        self.storage.write_json("normalized/execution_blocked_candidates.json", execution_blocked)
        candidate_packets = build_candidate_research_packets(
            top_for_overlay,
            overlays,
            top_n=int(research_cfg.get("max_candidate_packets", research_cfg.get("max_candidates_for_deep_mini", 5))),
        )
        self.storage.write_json("normalized/candidate_research_packets.json", candidate_packets)

        deep_cfg = self._deep_research_cfg()
        if skip_deep_mini:
            deep_cfg = {**deep_cfg, "enabled": False, "auto_run": False}
        live_deep_mini_required = deep_mini_required_for_live_research(deep_cfg, self.cfg.get("research_mode") or {})
        live_grok_required = grok_required_for_live_research(deep_cfg, self.cfg.get("research_mode") or {})
        governed_research_required = live_deep_mini_required or live_grok_required
        deep_errors = self._validate_deep_research_cfg(deep_cfg)
        if deep_errors:
            payload = {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "mode": "research_v2_config_error",
                "errors": deep_errors,
                "summary": {"status": "config_error", "deep_research_config_errors": deep_errors},
            }
            self.storage.write_json("meta/run_manifest.json", payload)
            raise ValueError(";".join(deep_errors))
        deep_mini_path = None
        deep_mini_run: dict[str, Any] | None = None
        daily_best_pick_packet: dict[str, Any] | None = None
        if deep_cfg.get("enabled", True):
            top_n = int(deep_cfg.get("top_n_for_deep_mini", 3))
            shortlist = execution_eligible[:top_n] or ranked[:top_n]
            if shortlist:
                deep_context = {
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "candidate_symbols": candidate_symbols,
                    "research_ranked_count": len(ranked),
                    "execution_eligible_count": len(execution_eligible),
                    "execution_blocked_count": len(execution_blocked),
                    "grok_social_context": load_grok_social_context(self.storage.root),
                }
                if deep_cfg.get("auto_run", True):
                    deep_context["execution_eligible"] = execution_eligible
                    deep_mini_result = run_governed_deep_mini(shortlist, deep_context, self.storage.path("deep_mini"), deep_cfg=deep_cfg)
                    deep_mini_path = deep_mini_result.prompt_path
                    deep_mini_run = deep_mini_result.to_dict()
                    daily_best_pick_packet = deep_mini_run.get("structured_packet")
                else:
                    deep_mini_path = write_deep_mini_input(shortlist, deep_context, self.storage.path("deep_mini"))

        if not daily_best_pick_packet:
            if governed_research_required:
                fallback_packet = build_deep_mini_required_no_trade_packet(
                    ranked,
                    generated_at_utc=datetime.now(timezone.utc).isoformat(),
                    reason=GROK_REQUIRED_BLOCKER if live_grok_required else DEEP_MINI_REQUIRED_BLOCKER,
                )
            else:
                fallback_packet = build_fallback_best_pick_packet(
                    ranked,
                    execution_eligible,
                    generated_at_utc=datetime.now(timezone.utc).isoformat(),
                    route_chosen=(deep_mini_run or {}).get("route_chosen"),
                    caveats=["governed_deep_mini_unavailable_or_not_run"] if not deep_mini_run else (["governed_deep_mini_unparsed"] if not (deep_mini_run or {}).get("structured_packet") else []),
                )
            daily_best_pick_packet = fallback_packet.to_dict()
        if governed_research_required:
            artifact_status = write_required_deep_mini_artifacts(
                self.storage.root,
                trading_date=self.storage.trading_day,
                broad_candidates=broad_candidates,
                shortlist=execution_eligible[: int(deep_cfg.get("top_n_for_deep_mini", 3))] or ranked[: int(deep_cfg.get("top_n_for_deep_mini", 3))],
                context={"candidate_symbols": candidate_symbols, "execution_eligible": execution_eligible, "grok_social_context": load_grok_social_context(self.storage.root)},
                deep_mini_run=deep_mini_run,
                final_packet=daily_best_pick_packet,
                incomplete_reason=None if deep_mini_run and deep_mini_run.get("structured_packet") else (GROK_REQUIRED_BLOCKER if live_grok_required else DEEP_MINI_REQUIRED_BLOCKER),
            )
            daily_best_pick_packet["deep_mini_required_for_live_research"] = True
            daily_best_pick_packet["grok_required_for_live_research"] = live_grok_required
            daily_best_pick_packet["deep_mini_artifact_status"] = artifact_status
        self.storage.write_json("normalized/daily_best_pick_packet.json", daily_best_pick_packet)
        primary_symbol = daily_best_pick_packet.get("best_pick") or daily_best_pick_packet.get("research_leader")
        source_lane_status = build_source_lane_status(all_events, primary_ticker=primary_symbol)
        self.storage.write_json("normalized/source_lane_status.json", source_lane_status)
        self.storage.write_json("source_lane_status.json", source_lane_status)
        trade_ticket = ticket_from_final_packet(
            daily_best_pick_packet,
            trading_date=self.storage.trading_day,
            generated_at_utc=datetime.now(timezone.utc).isoformat(),
            completed_before_deadline=bool((daily_best_pick_packet.get("deep_mini_artifact_status") or {}).get("completed")) if governed_research_required else False,
            research_model="o4-mini-deep-research" if str(deep_cfg.get("mode") or "deep_mini") == "deep_mini" else "o3-deep-research",
            source_breadth_status=(source_lane_status[0].get("status") if isinstance(source_lane_status, list) and source_lane_status and isinstance(source_lane_status[0], dict) else None),
        )
        ticket_validation = validate_ticket(trade_ticket)
        trade_ticket["valid"] = ticket_validation.valid
        trade_ticket["blockers"] = ticket_validation.blockers
        self.storage.write_json("trade_authorization_ticket.json", trade_ticket)

        summary = summarize_run(all_events, cluster_dicts, execution_eligible, execution_blocked)
        if deep_mini_run:
            summary.update(
                {
                    "deep_mini_status": deep_mini_run.get("status"),
                    "deep_mini_success": deep_mini_run.get("success"),
                    "deep_mini_route_chosen": deep_mini_run.get("route_chosen"),
                }
            )
        summary.update(
            {
                "discovery_events_count": len(discovery_events),
                "evidence_events_count": len(evidence_events),
                "discovered_symbols_count": len(candidate_symbols),
                **raw_discovery_summary,
                "broad_ai_discovery_candidate_count": len([row for row in broad_candidates if row.get("ticker")]),
                "research_ranked_count": len(ranked),
                "execution_eligible_count": len(execution_eligible),
                "execution_blocked_count": len(execution_blocked),
                "candidate_research_packets_count": len(candidate_packets),
                "execution_gate_skipped": execution_gate_skipped,
                "source_lane_status_count": len(source_lane_status),
            }
        )
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "tickers": candidate_symbols,
            "summary": summary,
            "mode": "research_v2",
            "artifacts": {
                "discovery_events": str(self.storage.path("raw/discovery_events.jsonl")),
                "raw_runner_candidates": str(self.storage.path("raw/raw_runner_candidates.json")),
                "top_raw_candidates": str(self.storage.path("raw/top_raw_candidates.json")),
                "first_seen_candidates": str(self.storage.path(FIRST_SEEN_PATH)),
                "broad_ai_discovery_candidates": str(self.storage.path("raw/broad_ai_discovery_candidates.json")),
                "broad_ai_discovery_sources": str(self.storage.path("raw/broad_ai_discovery_sources.jsonl")),
                "discovered_symbols": str(self.storage.path("normalized/discovered_symbols.json")),
                "research_ranked_candidates": str(self.storage.path("normalized/research_ranked_candidates.json")),
                "execution_eligible_candidates": str(self.storage.path("normalized/execution_eligible_candidates.json")),
                "candidate_research_packets": str(self.storage.path("normalized/candidate_research_packets.json")),
                "daily_best_pick_packet": str(self.storage.path("normalized/daily_best_pick_packet.json")),
                "source_lane_status": str(self.storage.path("normalized/source_lane_status.json")),
                "trade_authorization_ticket": str(self.storage.path("trade_authorization_ticket.json")),
                "deep_mini_input": str(deep_mini_path) if deep_mini_path else None,
                    "deep_mini_run": deep_mini_run,
                    "deep_mini_required_for_live_research": live_deep_mini_required,
                    "grok_required_for_live_research": live_grok_required,
                    "deep_mini_artifacts": daily_best_pick_packet.get("deep_mini_artifact_status") if isinstance(daily_best_pick_packet, dict) else None,
            },
        }
        self.storage.write_json("meta/run_manifest.json", manifest)
        return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Roi Snips research pipeline")
    parser.add_argument("--manual-symbols", default="", help="Comma-separated manual symbol override/include list")
    parser.add_argument("--discovery-only", action="store_true")
    parser.add_argument("--skip-overlays", action="store_true")
    parser.add_argument("--skip-deep-mini", action="store_true")
    args = parser.parse_args()
    manual_symbols = [s.strip().upper() for s in args.manual_symbols.split(",") if s.strip()] if args.manual_symbols else None
    print(json.dumps(ResearchPipeline().run_once(manual_symbols=manual_symbols, discovery_only=args.discovery_only, skip_overlays=args.skip_overlays, skip_deep_mini=args.skip_deep_mini), indent=2))


if __name__ == "__main__":
    main()
