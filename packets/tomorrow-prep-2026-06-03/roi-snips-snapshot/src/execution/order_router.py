"""Deterministic broker-aware order router for the autonomous live POC."""

from __future__ import annotations

import os
import fcntl
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..common.config import load_live_config, repo_root, risk_config_for_validation
from ..common.provider_factory import build_trade_adapter
from ..common.runtime_state import active_guards, session_phase
from ..research.trade_authorization_ticket import (
    final_arming_gate_path,
    load_ticket,
    load_today_ticket,
    validate_submission_against_ticket,
)
from ..risk.rules import validate_trade_plan
from .audit_logger import append_audit_event
from .position_manager import PositionManager
from .proposal_store import update_proposal


OPENING_MODES_REQUIRING_EXIT_MANAGER = {
    "OPENING_BURST_HYPER_LONG",
    "SOCIAL_TAPE_ROCKET",
    "PREMARKET_SURGE_LONG",
    "STAGED_OPEN_EXPLOSION_LONG",
    "PREMARKET_HIGH_RECLAIM_LONG",
    "OPENING_DRIVE_LONG",
    "ORB_BREAK",
    "ORB_BREAK_LONG",
    "VWAP_RECLAIM",
    "VWAP_RECLAIM_LONG",
    "SECOND_LEG_CONTINUATION",
    "SECOND_LEG_CONTINUATION_LONG",
}


class OrderRouter:
    def __init__(self, trade_adapter: Any | None = None, cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or load_live_config()
        self.trade_adapter = trade_adapter or build_trade_adapter(self.cfg)
        self.position_manager = PositionManager(self.trade_adapter, self.cfg)

    def _trade_runtime(self) -> dict[str, Any]:
        if hasattr(self.trade_adapter, "runtime_environment"):
            try:
                value = self.trade_adapter.runtime_environment()
                if isinstance(value, dict):
                    return value
                return {"_runtime_error": "runtime_environment_malformed"}
            except Exception as exc:
                return {"_runtime_error": f"runtime_environment_unavailable:{exc.__class__.__name__}"}
        return {"_runtime_error": "runtime_environment_unsupported"}

    def _submission_guard(self) -> tuple[str, str | None]:
        live_armed = os.getenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
        paper_armed = os.getenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false").strip().lower() in {"1", "true", "yes", "on"}
        runtime = self._trade_runtime()
        cfg_broker = self.cfg.get("broker") or {}
        cfg_environment = str(cfg_broker.get("environment") or "").strip().lower()
        runtime_environment = str(runtime.get("environment") or "").strip().lower()

        if live_armed and paper_armed:
            return "dry_run", "ambiguous_submission_arming"
        if live_armed:
            if cfg_environment and cfg_environment != "live":
                return "dry_run", "live_submission_cfg_mismatch"
            if runtime.get("_runtime_error") or not runtime_environment:
                return "dry_run", "live_submission_runtime_unavailable"
            if runtime_environment and runtime_environment != "live":
                return "dry_run", "live_submission_requires_live_broker"
            return "live", None
        if paper_armed:
            if cfg_environment and cfg_environment != "paper":
                return "dry_run", "paper_submission_cfg_mismatch"
            if runtime.get("_runtime_error") or not runtime_environment:
                return "dry_run", "paper_submission_runtime_unavailable"
            if runtime_environment and runtime_environment != "paper":
                return "dry_run", "paper_submission_requires_paper_broker"
            return "paper", None
        return "dry_run", None

    def _trade_authorization_required(self, submission_mode: str) -> bool:
        if submission_mode not in {"live", "paper"}:
            return False
        return True

    def _final_arming_readiness(self, trading_date: str | None = None) -> dict[str, Any] | None:
        path = final_arming_gate_path(repo_root(), trading_date)
        payload = load_ticket(path)
        if not payload:
            return None
        return {
            "status": payload.get("readiness_status"),
            "verdict": payload.get("verdict"),
            "armed_live": payload.get("armed_live"),
            "path": str(path),
        }

    def _validate_trade_authorization_ticket(self, plan: dict[str, Any], submission_mode: str) -> tuple[bool, str | None]:
        if not self._trade_authorization_required(submission_mode):
            return True, None
        root = repo_root()
        trading_date = str(plan.get("trade_date") or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))
        ticket = load_today_ticket(root, trading_date)
        readiness = self._final_arming_readiness(trading_date)
        ok, reason = validate_submission_against_ticket(plan, ticket, readiness)
        return ok, reason

    def submission_mode(self) -> str:
        return self._submission_guard()[0]

    def _live_enabled(self) -> bool:
        return self.submission_mode() == "live"

    def _allow_regular_bracket(self, plan: dict[str, Any]) -> bool:
        phase = session_phase(self.cfg)
        regular_ok = phase in {"ENTRY_WINDOW", "MANAGE_ONLY"}
        stable = bool(plan.get("target_1") and plan.get("stop"))
        return regular_ok and stable and bool(((self.cfg.get("execution") or {}).get("regular") or {}).get("use_bracket_when_stable", True))

    def _order_route(self, plan: dict[str, Any]) -> str:
        if self._allow_regular_bracket(plan):
            return "REGULAR_BRACKET"
        return "REGULAR_MARKETABLE_LIMIT"

    def _build_order(self, plan: dict[str, Any]) -> dict[str, Any]:
        route = self._order_route(plan)
        order = {
            "symbol": plan["ticker"],
            "side": "BUY",
            "mode": plan.get("mode"),
            "strategy": plan.get("strategy_family", "CatalystContinuationLong"),
            "trigger": plan.get("trigger"),
            "quantity": int(plan["shares"]),
            "notional_usd": plan.get("notional_usd"),
            "time_in_force": plan.get("time_in_force", "DAY"),
            "client_order_id": plan.get("client_order_id") or plan["plan_id"],
            "limit_price": plan.get("limit_price", plan.get("entry")),
            "entry_limit_price": plan.get("entry"),
            "hard_max_entry_price": plan.get("hard_max_entry_price") or plan.get("limit_price", plan.get("entry")),
            "initial_stop": plan.get("stop"),
            "stop_price": plan.get("stop"),
            "target_1": plan.get("target_1"),
            "target_2": plan.get("target_2"),
        }
        if route == "REGULAR_BRACKET":
            order.update({"order_type": plan.get("order_type", "LIMIT"), "extended_hours": False, "order_class": "BRACKET"})
        else:
            order.update({"order_type": "LIMIT", "extended_hours": False, "time_in_force": plan.get("time_in_force", "DAY")})
        return order

    @staticmethod
    def _parse_cash_value(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    def _submission_sentinel_path(self) -> Path:
        controls = self.cfg.get("controls") or {}
        proposals_dir = Path(controls.get("proposals_dir") or "state/proposals")
        return proposals_dir.parent / "live_order_submission_sentinel.json"

    def _submission_lock_path(self) -> Path:
        controls = self.cfg.get("controls") or {}
        proposals_dir = Path(controls.get("proposals_dir") or "state/proposals")
        return proposals_dir.parent / "live_order_submission.lock"

    @contextmanager
    def _submission_lock(self):
        path = self._submission_lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _active_submission_sentinel(self) -> dict[str, Any] | None:
        path = self._submission_sentinel_path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return {"status": "unknown", "reason": "submission_sentinel_unreadable", "path": str(path)}
        status = str(payload.get("status") or "")
        if status not in {"pending", "submitted"}:
            return None
        created_raw = payload.get("created_at_utc")
        if status == "submitted" and created_raw:
            try:
                created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                if created.astimezone(ZoneInfo("America/New_York")).date() != datetime.now(ZoneInfo("America/New_York")).date():
                    path.unlink(missing_ok=True)
                    return None
            except Exception:
                return payload
        if status == "pending" and created_raw:
            try:
                created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - created.astimezone(timezone.utc) > timedelta(minutes=30):
                    path.unlink(missing_ok=True)
                    return None
            except Exception:
                return payload
        return payload

    def _write_submission_sentinel(self, status: str, plan: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
        path = self._submission_sentinel_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "plan_id": plan.get("plan_id"),
            "ticker": plan.get("ticker"),
            **(extra or {}),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))

    def _clear_pending_submission_sentinel(self) -> None:
        path = self._submission_sentinel_path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return
        if payload.get("status") == "pending":
            path.unlink(missing_ok=True)

    def submit_order(self, plan: dict[str, Any], approval_text: str | None = None) -> dict[str, Any]:
        del approval_text
        plan_id = plan.get("plan_id")
        with self._submission_lock():
            sentinel = self._active_submission_sentinel()
            if sentinel:
                append_audit_event("order_blocked", {"reason": "existing_position_or_order_blocker:pending_submission", "plan_id": plan_id, "sentinel": sentinel}, status="blocked")
                update_proposal(plan_id, {"status": "blocked_pending_submission", "block_reason": "existing_position_or_order_blocker:pending_submission"}, self.cfg)
                return {"ok": False, "reason": "existing_position_or_order_blocker:pending_submission", "sentinel": sentinel}

            return self._submit_order_locked(plan)

    def _submit_order_locked(self, plan: dict[str, Any]) -> dict[str, Any]:
        plan_id = plan.get("plan_id")
        guards = active_guards(self.cfg)
        if guards["kill_switch"]:
            append_audit_event("order_blocked", {"reason": "kill_switch_active", "plan_id": plan_id}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_kill_switch", "block_reason": "kill_switch_active"}, self.cfg)
            return {"ok": False, "reason": "kill_switch_active"}
        if guards["disable_entries"]:
            append_audit_event("order_blocked", {"reason": "disable_entries_active", "plan_id": plan_id}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_disable_entries", "block_reason": "disable_entries_active"}, self.cfg)
            return {"ok": False, "reason": "disable_entries_active"}
        if guards["force_flat"]:
            append_audit_event("order_blocked", {"reason": "force_flat_phase", "plan_id": plan_id}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_force_flat", "block_reason": "force_flat_phase"}, self.cfg)
            return {"ok": False, "reason": "force_flat_phase"}
        if not guards["in_entry_window"]:
            append_audit_event("order_blocked", {"reason": "outside_entry_window", "plan_id": plan_id}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_outside_entry_window", "block_reason": "outside_entry_window"}, self.cfg)
            return {"ok": False, "reason": "outside_entry_window"}
        if str(plan.get("mode") or "").upper() in OPENING_MODES_REQUIRING_EXIT_MANAGER and not plan.get("opening_exit_manager_armed"):
            append_audit_event("order_blocked", {"reason": "opening_exit_manager_not_armed", "plan_id": plan_id}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_exit_manager", "block_reason": "opening_exit_manager_not_armed"}, self.cfg)
            return {"ok": False, "reason": "opening_exit_manager_not_armed"}

        submission_mode, submission_blocker = self._submission_guard()

        positions = self.position_manager.count_open_positions()
        if not positions.get("ok"):
            append_audit_event("order_blocked", {"reason": positions.get("reason"), "plan_id": plan_id}, status="blocked")
            return {"ok": False, "reason": positions.get("reason", "position_state_unavailable")}
        plan["open_positions"] = positions.get("count", 0)
        if int(plan["open_positions"] or 0) > 0:
            append_audit_event("order_blocked", {"reason": "existing_position_or_order_blocker:positions", "plan_id": plan_id, "positions": positions.get("positions")}, status="blocked")
            return {"ok": False, "reason": "existing_position_or_order_blocker:positions", "positions": positions.get("positions")}

        open_orders = self.trade_adapter.list_open_orders(limit=50) if hasattr(self.trade_adapter, "list_open_orders") else {"ok": True, "orders": []}
        if not open_orders.get("ok"):
            append_audit_event("order_blocked", {"reason": open_orders.get("reason"), "plan_id": plan_id}, status="blocked")
            return {"ok": False, "reason": open_orders.get("reason", "open_orders_unavailable")}
        active_orders = open_orders.get("orders") or []
        plan["open_orders"] = len(active_orders)
        if active_orders:
            append_audit_event("order_blocked", {"reason": "existing_position_or_order_blocker:open_orders", "plan_id": plan_id, "open_orders": active_orders}, status="blocked")
            return {"ok": False, "reason": "existing_position_or_order_blocker:open_orders", "open_orders": active_orders}

        get_account = getattr(self.trade_adapter, "get_account", None)
        if submission_mode in {"live", "paper"} and not callable(get_account):
            append_audit_event("order_blocked", {"reason": "account_state_unavailable", "plan_id": plan_id}, status="blocked")
            return {"ok": False, "reason": "account_state_unavailable"}
        account = get_account() if callable(get_account) else {"ok": True, "account": {}}
        if not account.get("ok"):
            append_audit_event("order_blocked", {"reason": account.get("reason"), "plan_id": plan_id}, status="blocked")
            return {"ok": False, "reason": account.get("reason", "account_state_unavailable")}
        acct = account.get("account") or {}
        notional_required = float(plan.get("notional_usd") or 0.0)
        cash_candidates = [acct.get("cash"), acct.get("buying_power"), acct.get("non_marginable_buying_power"), acct.get("regt_buying_power")]
        cash_values = [parsed for value in cash_candidates if (parsed := self._parse_cash_value(value)) is not None]
        if submission_mode in {"live", "paper"} and not cash_values:
            append_audit_event("order_blocked", {"reason": "cash_state_unavailable", "plan_id": plan_id, "account": acct}, status="blocked")
            return {"ok": False, "reason": "cash_state_unavailable"}
        available_cash = max(cash_values or [notional_required])
        settled_cash = acct.get("cash")
        if available_cash < notional_required:
            return {"ok": False, "reason": "insufficient_buying_power", "available_cash": available_cash, "notional_usd": notional_required}
        parsed_settled_cash = self._parse_cash_value(settled_cash)
        if settled_cash not in (None, "") and parsed_settled_cash is None:
            append_audit_event("order_blocked", {"reason": "cash_state_unavailable", "plan_id": plan_id, "account": acct}, status="blocked")
            return {"ok": False, "reason": "cash_state_unavailable"}
        if parsed_settled_cash is not None and parsed_settled_cash < min(notional_required, float(plan.get("cash_required_usd") or notional_required)):
            return {"ok": False, "reason": "insufficient_settled_cash", "cash": parsed_settled_cash, "notional_usd": notional_required}

        ok, reason = validate_trade_plan(plan, risk_config_for_validation(self.cfg))
        if not ok:
            append_audit_event("order_blocked", {"reason": reason, "plan": plan}, status="blocked")
            update_proposal(plan_id, {"status": "rejected_by_risk", "block_reason": reason}, self.cfg)
            return {"ok": False, "reason": reason}

        if submission_mode == "live" and not guards.get("live_armed"):
            append_audit_event("order_blocked", {"reason": "live_armed_missing", "plan_id": plan_id}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_live_armed_missing", "block_reason": "live_armed_missing"}, self.cfg)
            return {"ok": False, "reason": "live_armed_missing"}
        if submission_blocker:
            append_audit_event("order_blocked", {"reason": submission_blocker, "plan_id": plan_id, "runtime": self._trade_runtime()}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_submission_mode", "block_reason": submission_blocker}, self.cfg)
            return {"ok": False, "reason": submission_blocker}
        ticket_ok, ticket_reason = self._validate_trade_authorization_ticket(plan, submission_mode)
        if not ticket_ok:
            append_audit_event("order_blocked", {"reason": ticket_reason, "plan_id": plan_id, "ticker": plan.get("ticker")}, status="blocked")
            update_proposal(plan_id, {"status": "blocked_trade_authorization", "block_reason": ticket_reason}, self.cfg)
            return {"ok": False, "reason": ticket_reason}

        order = self._build_order(plan)
        if submission_mode in {"live", "paper"}:
            self._write_submission_sentinel("pending", plan, {"mode": submission_mode})
        append_audit_event("pre_preview", {"plan_id": plan_id, "symbol": plan["ticker"], "order": order})
        preview = self.trade_adapter.preview_order(order)
        append_audit_event("post_preview", {"plan_id": plan_id, "symbol": plan["ticker"], "order": order, "response": preview}, status="ok" if preview.get("ok") else "error")
        if not preview.get("ok"):
            self._clear_pending_submission_sentinel()
            update_proposal(plan_id, {"status": "preview_failed", "preview_error": preview.get("reason")}, self.cfg)
            return {"ok": False, "reason": preview.get("reason", "preview_failed"), "preview": preview}

        if submission_mode == "dry_run":
            self._clear_pending_submission_sentinel()
            update_proposal(plan_id, {"status": "previewed_dry_run", "preview": preview, "broker_order_route": self._order_route(plan)}, self.cfg)
            return {"ok": True, "mode": "dry_run", "preview": preview, "order": order}

        append_audit_event("pre_place", {"plan_id": plan_id, "symbol": plan["ticker"], "order": order})
        placed = self.trade_adapter.place_order(order)
        append_audit_event("post_place", {"plan_id": plan_id, "symbol": plan["ticker"], "order": order, "response": placed}, status="ok" if placed.get("ok") else "error")
        if not placed.get("ok"):
            self._clear_pending_submission_sentinel()
            update_proposal(plan_id, {"status": "place_failed", "place_error": placed.get("reason")}, self.cfg)
            return {"ok": False, "reason": placed.get("reason", "place_failed"), "preview": preview, "placement": placed}

        proposal_status = "submitted_live" if submission_mode == "live" else "submitted_paper"
        self._write_submission_sentinel("submitted", plan, {"mode": submission_mode, "placement": placed})
        update_proposal(plan_id, {"status": proposal_status, "preview": preview, "placement": placed, "broker_order_route": self._order_route(plan)}, self.cfg)
        return {"ok": True, "mode": submission_mode, "preview": preview, "placement": placed, "order": order}

    def cancel_order(self, broker_order_id: str, plan_id: str | None = None) -> dict[str, Any]:
        append_audit_event("pre_cancel", {"plan_id": plan_id, "broker_order_id": broker_order_id})
        res = self.trade_adapter.cancel_order(broker_order_id)
        append_audit_event("post_cancel", {"plan_id": plan_id, "broker_order_id": broker_order_id, "response": res}, status="ok" if res.get("ok") else "error")
        return res

    def query_order(self, broker_order_id: str, plan_id: str | None = None) -> dict[str, Any]:
        append_audit_event("pre_query", {"plan_id": plan_id, "broker_order_id": broker_order_id})
        res = self.trade_adapter.query_order(broker_order_id)
        append_audit_event("post_query", {"plan_id": plan_id, "broker_order_id": broker_order_id, "response": res}, status="ok" if res.get("ok") else "error")
        return res

    def replace_order(self, broker_order_id: str, fields: dict[str, Any], plan_id: str | None = None) -> dict[str, Any]:
        append_audit_event("pre_replace", {"plan_id": plan_id, "broker_order_id": broker_order_id, "fields": fields})
        res = self.trade_adapter.replace_order(broker_order_id, fields)
        append_audit_event("post_replace", {"plan_id": plan_id, "broker_order_id": broker_order_id, "response": res}, status="ok" if res.get("ok") else "error")
        return res
