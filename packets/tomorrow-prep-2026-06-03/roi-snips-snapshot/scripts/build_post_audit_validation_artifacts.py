#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.research import lifecycle as lc
from src.research.source_lane_status import build_source_lane_status


ROOT = Path(__file__).resolve().parents[1]
TRADE_DATE = "2026-05-22"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _source_lane_status() -> list[dict]:
    path = ROOT / "runs" / TRADE_DATE / "normalized" / "source_lane_status.json"
    rows = _load_json(path, None)
    if isinstance(rows, list) and rows:
        return rows
    return build_source_lane_status([])


def build_report() -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    source_lane_status = _source_lane_status()
    infq = {
        "symbol": "INFQ",
        "company_name": "Infleqtion",
        "catalyst_type": "government_contract",
        "claim_summary": "INFQ-style validated government/CHIPS quantum funding runner with heavy premarket repricing.",
        "research_priority_score": 8.9,
        "hyper_trade_score": 7.1,
        "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE", "DIRECT_POLICY_THEME_BENEFICIARY", "VERIFIED_CATALYST_RUNNER"],
        "last_price": 16.12,
        "gap_pct": 42.9,
        "premarket_volume": 8_770_000,
        "premarket_dollar_volume": 119_980_000,
        "spread_pct": 0.22,
        "execution_gate_pass": True,
        "execution_readiness_score": 88.0,
        "execution_blockers": [],
        "execution_warnings": [],
        "anti_chase_state": lc.SECOND_LEG_WATCH,
        "opportunity_lifecycle_state": lc.SECOND_LEG_WATCH,
        "entry_viability_score": 42.0,
    }
    same_style = [
        {
            "symbol": "QBTS",
            "company_name": "D-Wave Quantum",
            "catalyst_type": "theme_sympathy",
            "claim_summary": "Quantum same-theme runner backup, not mega-cap filler.",
            "research_priority_score": 7.1,
            "hyper_trade_score": 4.2,
            "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"],
            "gap_pct": 11.5,
            "premarket_dollar_volume": 8_500_000,
            "execution_gate_pass": True,
            "execution_blockers": [],
        },
        {
            "symbol": "RGTI",
            "company_name": "Rigetti Computing",
            "catalyst_type": "theme_sympathy",
            "claim_summary": "Quantum same-theme high-volatility backup.",
            "research_priority_score": 7.0,
            "hyper_trade_score": 4.0,
            "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"],
            "gap_pct": 9.4,
            "premarket_dollar_volume": 11_000_000,
            "execution_gate_pass": True,
            "execution_blockers": [],
        },
        {
            "symbol": "QUBT",
            "company_name": "Quantum Computing Inc.",
            "catalyst_type": "theme_sympathy",
            "claim_summary": "Quantum same-theme high-beta backup.",
            "research_priority_score": 6.7,
            "hyper_trade_score": 3.7,
            "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"],
            "gap_pct": 8.2,
            "premarket_dollar_volume": 4_500_000,
            "execution_gate_pass": True,
            "execution_blockers": [],
        },
        {
            "symbol": "IONQ",
            "company_name": "IonQ",
            "catalyst_type": "theme_sympathy",
            "claim_summary": "Quantum same-theme liquid backup.",
            "research_priority_score": 6.4,
            "hyper_trade_score": 3.3,
            "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"],
            "gap_pct": 5.8,
            "premarket_dollar_volume": 20_000_000,
            "execution_gate_pass": True,
            "execution_blockers": [],
        },
    ]
    backup_pool_diagnostics = {
        "same_style_candidates_considered": [
            {"symbol": row["symbol"], "selected": True, "mega_cap": False, "reasons": ["same_theme_policy_theme_runner", "high_volatility_backup"]}
            for row in same_style
        ],
        "same_style_candidates_selected": [row["symbol"] for row in same_style[:3]],
        "mega_cap_backups_used": [],
        "reason_mega_cap_backup_used": None,
        "source_lane_failures_affecting_backups": [],
    }
    return {
        "generated_at_utc": generated_at,
        "status": "post_audit_validation",
        "validation_mode": "captured_INFQ_fixture_no_order",
        "orders_allowed": False,
        "orders_submitted": False,
        "research_leader": infq,
        "executable_primary": None,
        "watch_only": [],
        "second_leg_watch": [infq],
        "no_trade_extended": [],
        "anti_chase_state": lc.SECOND_LEG_WATCH,
        "opportunity_lifecycle_state": lc.SECOND_LEG_WATCH,
        "entry_viability_score": infq["entry_viability_score"],
        "same_style_backup_status": {
            "leader": "INFQ",
            "same_style_non_megacap_backups": [row["symbol"] for row in same_style],
            "megacap_default_backups": [],
            "same_style_backup_pool_ok": True,
            "reason": None,
            "backup_pool_diagnostics": backup_pool_diagnostics,
        },
        "backup_pool_diagnostics": backup_pool_diagnostics,
        "source_lane_status": source_lane_status,
        "best_pick_candidate": infq,
        "best_pick_packet": {
            "best_pick": "INFQ",
            "research_leader": "INFQ",
            "source_mode": "post_audit_validation_fixture",
            "caveats": ["execution intentionally blocked until continuation criteria and future no-order validation pass"],
        },
        "watchlist": {"A": [infq], "B": same_style[:3], "C": same_style[3:]},
        "research_ranked": [infq, *same_style],
        "execution_watchlist": same_style[:1],
        "candidate_research_packets": [],
        "no_trade_list": [],
    }


def write_artifacts(report: dict) -> tuple[Path, Path]:
    json_path = ROOT / "reports" / "morning" / "json" / f"{TRADE_DATE}_post_audit_validation.json"
    md_path = ROOT / "reports" / "morning" / "md" / f"{TRADE_DATE}_post_audit_validation.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    lines = [
        "# Roi Snips Post-Audit Validation",
        "",
        f"Generated: {report['generated_at_utc']}",
        "Mode: captured INFQ fixture, no orders",
        "",
        "## Research / Execution Separation",
        f"- research_leader: {report['research_leader']['symbol']}",
        "- executable_primary: none",
        f"- anti_chase_state: {report['anti_chase_state']}",
        f"- lifecycle: {report['opportunity_lifecycle_state']}",
        f"- entry_viability_score: {report['entry_viability_score']}",
        "",
        "## Same-Style Backups",
        f"- selected: {', '.join(report['same_style_backup_status']['same_style_non_megacap_backups'])}",
        "- mega-cap backups used: none",
        "",
        "## Source Lane Status",
    ]
    for row in report["source_lane_status"]:
        lines.append(
            f"- {row.get('lane_name')}: configured={row.get('configured')} ran={row.get('ran')} "
            f"candidates={row.get('produced_candidates_count')} useful={row.get('produced_useful_evidence_count')}"
        )
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def main() -> int:
    report = build_report()
    json_path, md_path = write_artifacts(report)
    print(json.dumps({"ok": True, "json": str(json_path), "md": str(md_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
