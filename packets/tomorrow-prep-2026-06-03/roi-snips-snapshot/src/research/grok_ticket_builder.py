from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .trade_authorization_ticket import BLOCKED_DEFAULT_MEGACAPS, validate_ticket


GROK_RESEARCH_ONLY_BLOCKER = "grok_research_only_not_live_authorizer"


def create_grok_trade_authorization_ticket(
    tournament: dict[str, Any] | None,
    red_team: dict[str, Any] | None,
    *,
    trading_date: str,
    model: str = "grok-4.3",
    ticket_candidate_path: str = "grok/ticket_candidate.json",
    final_packet_path: str = "grok/d_research_tournament.json",
) -> dict[str, Any]:
    tournament = tournament or {}
    red_team = red_team or {}
    candidate = tournament.get("authorized_candidate") or {}
    ticker = str(candidate.get("ticker") or "").upper() or None
    blockers = []
    research_recommended = tournament.get("decision") in {"AUTHORIZE_ONE", "RECOMMEND_FOR_DEEP_MINI_REVIEW"} and ticker and not red_team.get("should_block_ticket")
    status = "INVALID" if research_recommended else "NO_TRADE"
    blockers.append(GROK_RESEARCH_ONLY_BLOCKER)
    if tournament.get("decision") not in {"AUTHORIZE_ONE", "RECOMMEND_FOR_DEEP_MINI_REVIEW"}:
        blockers.append(tournament.get("no_trade_reason") or "grok_no_trade")
    if red_team.get("should_block_ticket"):
        blockers.extend(red_team.get("fatal_flaws") or ["grok_red_team_failed"])
    if tournament.get("research_only_backups") and tournament.get("backup_execution_allowed"):
        blockers.append("backup_execution_not_allowed")
    mega_exception = bool(candidate.get("mega_cap_exception") or tournament.get("mega_cap_exception"))
    if ticker in BLOCKED_DEFAULT_MEGACAPS and not mega_exception:
        status = "INVALID"
        blockers.append("mega_cap_backup_not_authorized")
    stale_exception = bool(candidate.get("stale_prior_winner_exception") or tournament.get("stale_prior_winner_exception"))
    generated = datetime.now(timezone.utc).isoformat()
    strategy = str(candidate.get("strategy") or ("NO_TRADE" if status != "AUTHORIZED" else "OPENING_BURST_HYPER_LONG")).upper()
    ticket = {
        "ticket_id": f"{trading_date}-{ticker or 'NO_TRADE'}",
        "trade_date": trading_date,
        "trading_date": trading_date,
        "generated_at_utc": generated,
        "created_at_utc": generated,
        "expires_at_utc": f"{trading_date}T20:00:00+00:00",
        "completed_before_deadline": True,
        "research_model": model,
        "authorizer": "grok_d_research",
        "grok_research_only": True,
        "can_authorize_live_trade": False,
        "deep_research_required": True,
        "deep_research_completed": status == "AUTHORIZED",
        "deep_research_artifacts": {"final_packet": final_packet_path, "ticket_candidate": ticket_candidate_path},
        "status": status,
        "authorized_for_live_consideration": False,
        "authorized_ticker": None,
        "company": candidate.get("company"),
        "authorized_strategy": strategy,
        "strategy": strategy,
        "research_leader": tournament.get("research_leader"),
        "research_recommended_ticker": ticker if research_recommended else None,
        "executable_primary": None,
        "backup_tickers_authorized_for_live": [],
        "backups_research_only": tournament.get("research_only_backups") or [],
        "backup_execution_allowed": False,
        "deterministic_fallback_used": False,
        "deterministic_fallback_executable_allowed": False,
        "requires_live_tape_confirmation": True,
        "mega_cap_exception": mega_exception,
        "exceptional_mega_cap_test_passed": mega_exception,
        "stale_prior_winner_exception": stale_exception,
        "stale_prior_winner_check": "PASS" if stale_exception else candidate.get("stale_prior_winner_check", "PASS"),
        "entry_conditions": [candidate.get("buy_range_or_wait_trigger")] if candidate.get("buy_range_or_wait_trigger") else [],
        "must_not_trade_if": candidate.get("must_not_trade_if") or [],
        "thesis_break": candidate.get("thesis_break"),
        "hard_stop_or_thesis_break": candidate.get("thesis_break"),
        "targets": [candidate.get("same_day_target"), candidate.get("one_to_three_day_target")],
        "buy_now_allowed_from_research": False,
        "buy_now_allowed": False,
        "blockers": sorted({str(item) for item in blockers if item}),
    }
    validation = validate_ticket(ticket)
    ticket["valid"] = validation.valid
    ticket["blockers"] = validation.blockers if not validation.valid else []
    if status == "NO_TRADE" and not ticket["blockers"]:
        ticket["blockers"] = ["ticket_no_trade"]
    return ticket


def create_grok_ticket_input_summary(
    tournament: dict[str, Any] | None,
    red_team: dict[str, Any] | None,
    *,
    trading_date: str,
    model: str = "grok-4.3",
) -> dict[str, Any]:
    ticket_candidate = create_grok_trade_authorization_ticket(
        tournament,
        red_team,
        trading_date=trading_date,
        model=model,
    )
    tournament = tournament or {}
    red_team = red_team or {}
    candidate = tournament.get("authorized_candidate") or {}
    ticker = str(candidate.get("ticker") or "").upper() or None
    return {
        "stage": "grok_ticket_input_summary",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trading_date": trading_date,
        "model": model,
        "grok_research_only": True,
        "can_authorize_live_trade": False,
        "can_create_live_executable_primary": False,
        "research_recommended_ticker": ticker,
        "names_for_deep_mini_to_judge": [ticker] if ticker else [],
        "candidate_recommendations": [candidate] if candidate else [],
        "red_team": red_team,
        "ticket_candidate_invalid_for_live": ticket_candidate,
        "live_authorization_rule": "Deep-mini/governed deep research must create the only live-valid ticket.",
    }


def create_no_trade_ticket(*, trading_date: str, reason: str, model: str = "grok-4.3") -> dict[str, Any]:
    return create_grok_trade_authorization_ticket(
        {"decision": "NO_TRADE", "no_trade_reason": reason},
        {"should_block_ticket": True, "fatal_flaws": [reason]},
        trading_date=trading_date,
        model=model,
    )
