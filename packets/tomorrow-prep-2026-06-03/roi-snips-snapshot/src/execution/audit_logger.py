"""Audit logging with Postgres-first persistence and file fallback."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _journal_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    journal = root / "reports" / "journal" / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    return journal


def _append_file(record: dict[str, Any]) -> Path:
    journal = _journal_path()
    with journal.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return journal


def _append_postgres(record: dict[str, Any]) -> bool:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        return False
    try:
        import psycopg  # type: ignore
    except Exception:
        return False

    try:
        payload = record.get("payload") or {}
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO order_audit_log (plan_id, symbol, event_type, status, payload)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        payload.get("plan_id") or record.get("plan_id"),
                        payload.get("symbol") or payload.get("ticker"),
                        record.get("event_type"),
                        record.get("status", "ok"),
                        json.dumps(payload, default=str),
                    ),
                )
            conn.commit()
        return True
    except Exception:
        return False


def append_audit_event(event_type: str, payload: dict[str, Any], status: str = "ok") -> Path:
    record = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "status": status,
        "payload": payload,
    }
    persisted_pg = _append_postgres(record)
    record["persisted_to_postgres"] = persisted_pg
    return _append_file(record)


def append_operator_event(event_type: str, payload: dict[str, Any], status: str = "ok") -> Path:
    return append_audit_event(f"operator_{event_type}", payload, status=status)
