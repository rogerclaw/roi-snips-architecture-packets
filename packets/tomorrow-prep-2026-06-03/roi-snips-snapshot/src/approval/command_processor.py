from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.config import controls_paths, load_live_config
from ..common.runtime_state import activate_flag, clear_flag
from ..execution.audit_logger import append_operator_event
from ..execution.order_router import OrderRouter
from ..execution.position_manager import PositionManager
from ..execution.proposal_store import load_proposal, update_proposal
from .approval_gate import parse_operator_command


class CommandProcessor:
    def __init__(self, cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or load_live_config()
        self.router = OrderRouter(cfg=self.cfg)
        self.position_manager = PositionManager(self.router.trade_adapter)

    def _persist_operator_event(self, text: str, result: dict[str, Any]) -> Path:
        root = controls_paths(self.cfg)["operator_events_dir"]
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        with path.open("a") as f:
            f.write(json.dumps({"ts_utc": datetime.now(timezone.utc).isoformat(), "command": text, "result": result}) + "\n")
        return path

    def _persist_operator_command_postgres(self, text: str, source: str, action: str, plan_id: str | None, result: dict[str, Any]) -> None:
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
                        INSERT INTO operator_commands (source, action, plan_id, payload)
                        VALUES (%s, %s, %s, %s::jsonb)
                        """,
                        (source, action, plan_id, json.dumps({"command": text, "result": result})),
                    )
                conn.commit()
        except Exception:
            return

    def process(self, text: str, source: str = "operator") -> dict[str, Any]:
        decision = parse_operator_command(text)
        payload: dict[str, Any] = {"command": text, "action": decision.action, "source": source}

        if decision.action == "EXECUTE_ENTRY" and decision.plan_id:
            plan = load_proposal(decision.plan_id, self.cfg)
            result = self.router.submit_order(plan, approval_text=text)
            update_proposal(decision.plan_id, {"last_operator_command": text}, self.cfg)
        elif decision.action == "REJECT_ENTRY" and decision.plan_id:
            update_proposal(decision.plan_id, {"status": "rejected_by_operator", "operator_reason": decision.reason}, self.cfg)
            result = {"ok": True, "status": "rejected", "plan_id": decision.plan_id, "reason": decision.reason}
        elif decision.action == "DISABLE_NEW_ENTRIES":
            activate_flag("disable_entries", reason=f"source={source}; command={text}", cfg=self.cfg)
            result = {"ok": True, "status": "entries_disabled"}
        elif decision.action == "ENABLE_NEW_ENTRIES":
            clear_flag("disable_entries", self.cfg)
            result = {"ok": True, "status": "entries_enabled"}
        elif decision.action == "FLAT_ALL_NOW":
            cancel_res = self.position_manager.cancel_all_open_orders()
            flat_res = self.position_manager.flatten_all_positions(live_enabled=self.router.submission_mode() in {"paper", "live"})
            result = {"ok": cancel_res.get("ok") and flat_res.get("ok"), "cancel": cancel_res, "flatten": flat_res}
        elif decision.action == "ACK_ALERT":
            result = {"ok": True, "status": "alert_acknowledged", "alert_id": decision.alert_id}
        elif decision.action == "STATUS":
            submission_mode = self.router.submission_mode()
            result = {
                "ok": True,
                "status": "ready",
                "live_order_submission_enabled": submission_mode == "live",
                "paper_order_submission_enabled": submission_mode == "paper",
                "broker_submission_mode": submission_mode,
            }
        else:
            result = {"ok": False, "reason": "unknown_command"}

        payload["result"] = result
        append_operator_event("command", payload, status="ok" if result.get("ok") else "error")
        self._persist_operator_event(text, result)
        self._persist_operator_command_postgres(text, source, decision.action, decision.plan_id, result)
        return result


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print(json.dumps({"ok": False, "reason": "missing_command"}))
        return 1
    text = " ".join(argv)
    result = CommandProcessor().process(text)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
