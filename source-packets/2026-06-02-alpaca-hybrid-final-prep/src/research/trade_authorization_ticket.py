from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .strategy_fit import MEGA_CAPS


BLOCKED_DEFAULT_MEGACAPS = set(MEGA_CAPS) | {"SPY", "QQQ"}
VALID_STATUSES = {"AUTHORIZED", "NO_TRADE", "INVALID", "EXPIRED"}
VALID_STRATEGIES = {
    "OPENING_BURST_HYPER_LONG",
    "GAP_AND_GO_CONFIRMATION",
    "PREMARKET_HIGH_RECLAIM",
    "VWAP_WASHOUT_RECLAIM",
    "VWAP_RECLAIM",
    "ORB_BREAK",
    "ORB_BREAK_1MIN",
    "ORB_BREAK_5MIN",
    "SECOND_LEG_CONTINUATION",
    "EVENT_TIMED_HEADLINE_REACTION",
    "EVENT_PREPOSITION_STARTER",
    "NO_TRADE",
}
ALLOWED_LIVE_TICKET_AUTHORIZERS = {
    "openai_deep_mini",
    "openai_deep_research",
    "governed_deep_research",
}
DISALLOWED_LIVE_TICKET_AUTHORIZERS = {
    "grok_d_research",
    "grok_x_heat_radar",
    "grok_web_verification",
    "grok_first_d_research",
    "deterministic_fallback",
    "internal_ranking",
    "social_only",
}


@dataclass
class TicketValidation:
    valid: bool
    status: str
    blockers: list[str] = field(default_factory=list)
    ticket: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ticket_path_for_date(repo_root: Path, trading_date: str | None = None) -> Path:
    override = os.getenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", "").strip()
    if override:
        return Path(override)
    if not trading_date:
        trading_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    return repo_root / "runs" / trading_date / "trade_authorization_ticket.json"


def final_arming_gate_path(repo_root: Path, trading_date: str | None = None) -> Path:
    override = os.getenv("ROI_SNIPS_FINAL_ARMING_GATE_PATH", "").strip()
    if override:
        return Path(override)
    if not trading_date:
        trading_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    return repo_root / "reports" / "readiness" / f"final_live_arming_gate_{trading_date}.json"


def load_ticket(path: str | Path) -> dict[str, Any] | None:
    resolved = Path(path)
    if not resolved.exists():
        return None
    try:
        payload = json.loads(resolved.read_text())
    except Exception:
        return {"status": "INVALID", "blockers": ["ticket_json_unreadable"], "_path": str(resolved)}
    return payload if isinstance(payload, dict) else {"status": "INVALID", "blockers": ["ticket_not_json_object"], "_path": str(resolved)}


def load_today_ticket(repo_root: Path, trading_date: str | None = None) -> dict[str, Any] | None:
    return load_ticket(ticket_path_for_date(repo_root, trading_date))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


def _symbol(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _deadline_passed(ticket: dict[str, Any], now: datetime) -> bool:
    if ticket.get("completed_before_deadline") is False:
        return True
    expires = _parse_dt(ticket.get("expires_at_utc"))
    return bool(expires and now.astimezone(timezone.utc) > expires)


def validate_ticket(ticket: dict[str, Any] | None, now: datetime | None = None) -> TicketValidation:
    now = now or datetime.now(timezone.utc)
    if not ticket:
        return TicketValidation(False, "MISSING", ["no_valid_trade_authorization_ticket"], {})

    blockers = list(ticket.get("blockers") or [])
    status = str(ticket.get("status") or ("AUTHORIZED" if ticket.get("authorized_for_live_consideration") else "INVALID")).upper()
    ticker = _symbol(ticket.get("authorized_ticker"))
    strategy = str(ticket.get("authorized_strategy") or ticket.get("strategy") or "").upper()
    authorizer = str(ticket.get("authorizer") or "").strip()

    if status not in VALID_STATUSES:
        blockers.append("ticket_status_invalid")
    if _deadline_passed(ticket, now):
        status = "EXPIRED"
        blockers.append("ticket_expired")
    if ticket.get("completed_before_deadline") is not True:
        blockers.append("deep_research_ticket_invalid_or_late")
    if ticket.get("deep_research_required", True) is True and ticket.get("deep_research_completed", ticket.get("deep_research_status") == "completed") is not True:
        blockers.append("deep_research_required_for_live_not_completed")
    artifacts = ticket.get("deep_research_artifacts") or {}
    if ticket.get("deep_research_required", True) is True and not (artifacts.get("final_packet") or ticket.get("deep_research_request_id")):
        blockers.append("deep_research_final_packet_missing")
    if ticket.get("deterministic_fallback_executable_allowed") is True or ticket.get("deterministic_fallback_used") is True:
        blockers.append("deterministic_fallback_not_executable")
    if ticket.get("backup_execution_allowed") is True:
        blockers.append("backup_execution_not_allowed")
    if ticket.get("backup_tickers_authorized_for_live"):
        blockers.append("backup_execution_not_allowed")
    if status == "AUTHORIZED":
        if not authorizer:
            blockers.append("ticket_authorizer_missing")
        elif authorizer in DISALLOWED_LIVE_TICKET_AUTHORIZERS or authorizer not in ALLOWED_LIVE_TICKET_AUTHORIZERS:
            blockers.append("ticket_authorizer_not_allowed_for_live")
        if not ticker:
            blockers.append("authorized_ticket_missing_ticker")
        if strategy not in VALID_STRATEGIES:
            blockers.append("authorized_strategy_invalid")
        if ticker in BLOCKED_DEFAULT_MEGACAPS and ticket.get("exceptional_mega_cap_test_passed") is not True and ticket.get("mega_cap_exception") is not True:
            blockers.append("mega_cap_backup_not_authorized")
        if ticket.get("stale_prior_winner_check") == "FAIL" and ticket.get("stale_prior_winner_exception") is not True:
            blockers.append("stale_prior_winner_not_exception_authorized")
    if status == "NO_TRADE" and ticker:
        blockers.append("no_trade_ticket_has_ticker")

    valid = status == "AUTHORIZED" and not blockers
    if status == "NO_TRADE" and not blockers:
        blockers.append("ticket_no_trade")
    return TicketValidation(valid, status, sorted(set(blockers)), ticket)


def ticket_authorizes_symbol(ticket: dict[str, Any] | None, symbol: str, now: datetime | None = None) -> bool:
    validation = validate_ticket(ticket, now=now)
    return validation.valid and _symbol(symbol) == _symbol((ticket or {}).get("authorized_ticker"))


def ticket_is_live_executable(ticket: dict[str, Any] | None, now: datetime | None = None) -> bool:
    return validate_ticket(ticket, now=now).valid


def ticket_from_final_packet(
    packet: dict[str, Any],
    *,
    trading_date: str,
    generated_at_utc: str | None = None,
    completed_before_deadline: bool = True,
    research_model: str = "o4-mini-deep-research",
    source_breadth_status: str | None = None,
    same_style_backup_pool_ok: bool | None = None,
) -> dict[str, Any]:
    auth = packet.get("trade_authorization") or {}
    artifact_paths = packet.get("deep_mini_artifact_paths") or {}
    ticker = _symbol(auth.get("ticker") or auth.get("authorized_ticker") or packet.get("best_pick") or packet.get("ticker"))
    status = "AUTHORIZED" if auth.get("authorized", auth.get("authorized_for_live_consideration", bool(ticker))) and ticker else "NO_TRADE"
    strategy = str(auth.get("authorized_strategy") or packet.get("authorized_strategy") or packet.get("strategy") or "SECOND_LEG_CONTINUATION").upper()
    if status == "NO_TRADE":
        strategy = "NO_TRADE"
    return {
        "ticket_id": f"{trading_date}-{ticker or 'NO_TRADE'}",
        "trade_date": trading_date,
        "trading_date": trading_date,
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
        "created_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
        "expires_at_utc": f"{trading_date}T20:00:00+00:00",
        "completed_before_deadline": completed_before_deadline,
        "research_model": research_model,
        "authorizer": (
            "openai_deep_mini"
            if str(research_model) == "o4-mini-deep-research"
            else ("openai_deep_research" if not str(research_model).startswith("grok") else "grok_d_research")
        ),
        "deep_research_required": True,
        "deep_research_completed": status == "AUTHORIZED",
        "deep_research_request_id": auth.get("deep_research_request_id") or packet.get("route_chosen") or "local_deep_research_packet",
        "deep_research_artifacts": {
            "broad_discovery_summary": artifact_paths.get("broad_discovery_summary_json") or artifact_paths.get("broad_discovery_summary.json"),
            "shortlist_synthesis_summary": artifact_paths.get("shortlist_synthesis_summary_json") or artifact_paths.get("shortlist_synthesis_summary.json"),
            "red_team_summary": artifact_paths.get("red_team_summary_json") or artifact_paths.get("red_team_summary.json"),
            "final_packet": artifact_paths.get("final_packet_json") or artifact_paths.get("final_packet.json") or "normalized/daily_best_pick_packet.json",
        },
        "status": status,
        "authorized_for_live_consideration": status == "AUTHORIZED",
        "authorized_ticker": ticker if status == "AUTHORIZED" else None,
        "company": packet.get("company"),
        "authorized_strategy": strategy,
        "strategy": strategy,
        "research_leader": packet.get("research_leader") or ticker,
        "executable_primary": ticker if status == "AUTHORIZED" else None,
        "backup_tickers_authorized_for_live": [],
        "backups_research_only": packet.get("ranked_backups") or packet.get("same_style_backups") or [],
        "backup_execution_allowed": False,
        "source_breadth_status": source_breadth_status or packet.get("source_breadth_status") or "UNKNOWN",
        "same_style_backup_pool_ok": same_style_backup_pool_ok if same_style_backup_pool_ok is not None else packet.get("same_style_backup_pool_ok", True),
        "stale_prior_winner_check": packet.get("stale_prior_winner_check") or "PASS",
        "mega_cap_default_check": "FAIL" if ticker in BLOCKED_DEFAULT_MEGACAPS and packet.get("exceptional_mega_cap_test_passed") is not True else ("NOT_APPLICABLE" if ticker not in BLOCKED_DEFAULT_MEGACAPS else "PASS"),
        "exceptional_mega_cap_test_passed": packet.get("exceptional_mega_cap_test_passed") is True,
        "mega_cap_exception": packet.get("exceptional_mega_cap_test_passed") is True,
        "buy_now_allowed_from_research": False,
        "buy_now_allowed": False,
        "requires_live_tape_confirmation": True,
        "entry_cap": packet.get("entry_cap"),
        "hard_stop_or_thesis_break": packet.get("thesis_break_level") or packet.get("thesis_break"),
        "target_1": packet.get("same_day_upside_target"),
        "target_2": packet.get("one_to_three_day_upside_target"),
        "time_stop": packet.get("time_stop") or "11:00 ET",
        "force_flat_time": "15:45",
        "deterministic_fallback_used": packet.get("source_mode") == "internal_fallback",
        "deterministic_fallback_executable_allowed": False,
        "valid": True,
        "blockers": [],
    }


def validate_submission_against_ticket(
    proposal: dict[str, Any],
    ticket: dict[str, Any] | None,
    readiness: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    validation = validate_ticket(ticket, now=now)
    if not validation.valid:
        return False, validation.blockers[0] if validation.blockers else "deep_research_ticket_invalid_or_late"
    proposal_ticker = _symbol(proposal.get("ticker") or proposal.get("symbol"))
    authorized = _symbol(ticket.get("authorized_ticker"))
    if proposal_ticker != authorized:
        return False, "unauthorized_ticker_not_in_deep_research_ticket"
    proposal_mode = str(proposal.get("mode") or proposal.get("trigger") or "").upper()
    authorized_strategy = str(ticket.get("authorized_strategy") or ticket.get("strategy") or "").upper()
    allowed = {authorized_strategy, *(str(item).upper() for item in ticket.get("allowed_strategy_family") or [])}
    if authorized_strategy and proposal_mode and proposal_mode not in allowed:
        if not (authorized_strategy == "ORB_BREAK" and proposal_mode in {"ORB_BREAK", "ORB_BREAK_LONG", "ORB_BREAK_1MIN", "ORB_BREAK_5MIN"}):
            if not (authorized_strategy == "VWAP_RECLAIM" and proposal_mode in {"VWAP_RECLAIM", "VWAP_RECLAIM_LONG", "VWAP_WASHOUT_RECLAIM"}):
                return False, "authorized_strategy_mismatch"
    if readiness and readiness.get("status") != "GREEN":
        return False, "final_readiness_not_green"
    if proposal_ticker in BLOCKED_DEFAULT_MEGACAPS and ticket.get("exceptional_mega_cap_test_passed") is not True and ticket.get("mega_cap_exception") is not True:
        return False, "mega_cap_backup_not_authorized"
    return True, None
