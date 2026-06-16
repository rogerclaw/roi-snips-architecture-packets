from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..common.config import controls_paths, load_live_config


def proposals_dir(cfg: dict[str, Any] | None = None) -> Path:
    return controls_paths(cfg or load_live_config())["proposals_dir"]


def proposal_path(plan_id: str, cfg: dict[str, Any] | None = None) -> Path:
    return proposals_dir(cfg) / f"{plan_id}.json"


def _save_proposal_postgres(proposal: dict[str, Any]) -> None:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        return
    try:
        import psycopg  # type: ignore
    except Exception:
        return
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trade_proposals (plan_id, ticker, status, proposal_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (plan_id) DO UPDATE SET
                      ticker = EXCLUDED.ticker,
                      status = EXCLUDED.status,
                      proposal_json = EXCLUDED.proposal_json
                    """,
                    (
                        proposal["plan_id"],
                        proposal.get("ticker"),
                        proposal.get("status", "ready_for_execution"),
                        json.dumps(proposal, default=str),
                    ),
                )
            conn.commit()
    except Exception:
        return



def save_proposal(proposal: dict[str, Any], cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_live_config()
    plan_id = proposal["plan_id"]
    path = proposal_path(plan_id, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(proposal)
    record.setdefault("updated_at_utc", datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str))
    _save_proposal_postgres(record)
    return path


def load_proposal(plan_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    path = proposal_path(plan_id, cfg)
    return json.loads(path.read_text())


def update_proposal(plan_id: str, patch: dict[str, Any], cfg: dict[str, Any] | None = None) -> Path:
    data = load_proposal(plan_id, cfg)
    data.update(patch)
    data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    return save_proposal(data, cfg)


def list_proposals(status: str | None = None, cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    root = proposals_dir(cfg)
    if not root.exists():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            proposal = json.loads(path.read_text())
        except Exception:
            continue
        if status and proposal.get("status") != status:
            continue
        results.append(proposal)
    results.sort(key=lambda item: item.get("created_at_utc", ""), reverse=True)
    return results



def find_recent_matching_proposal(
    ticker: str,
    trigger: str,
    statuses: set[str] | None = None,
    max_age_minutes: int = 30,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    statuses = statuses or {"ready_for_execution", "previewed_dry_run", "submitted_live"}
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    for proposal in list_proposals(cfg=cfg):
        if str(proposal.get("ticker", "")).upper() != ticker.upper():
            continue
        if str(proposal.get("trigger", "")) != trigger:
            continue
        if proposal.get("status") not in statuses:
            continue
        created_raw = proposal.get("created_at_utc") or ""
        try:
            created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            created = None
        if created and created < cutoff:
            continue
        return proposal
    return None
