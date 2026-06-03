from datetime import datetime, timedelta, timezone

from src.research.trade_authorization_ticket import (
    ticket_authorizes_symbol,
    ticket_is_live_executable,
    validate_ticket,
)


def valid_ticket(ticker="INFQ"):
    return {
        "status": "AUTHORIZED",
        "authorizer": "openai_deep_mini",
        "authorized_ticker": ticker,
        "authorized_strategy": "ORB_BREAK",
        "completed_before_deadline": True,
        "deep_research_completed": True,
        "deep_research_artifacts": {"final_packet": "final.json"},
        "deterministic_fallback_executable_allowed": False,
        "backup_execution_allowed": False,
        "same_style_backup_pool_ok": True,
    }


def test_no_ticket_means_no_authorization():
    result = validate_ticket(None)
    assert result.valid is False
    assert "no_valid_trade_authorization_ticket" in result.blockers


def test_infq_ticket_authorizes_only_infq():
    ticket = valid_ticket("INFQ")
    assert ticket_is_live_executable(ticket) is True
    assert ticket_authorizes_symbol(ticket, "INFQ") is True
    assert ticket_authorizes_symbol(ticket, "NVDA") is False


def test_no_trade_ticket_authorizes_nothing():
    ticket = {**valid_ticket(None), "status": "NO_TRADE", "authorized_ticker": None}
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "ticket_no_trade" in result.blockers
    assert ticket_authorizes_symbol(ticket, "INFQ") is False


def test_nvda_requires_exceptional_mega_cap_authorization():
    ticket = valid_ticket("NVDA")
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "mega_cap_backup_not_authorized" in result.blockers
    ticket["exceptional_mega_cap_test_passed"] = True
    assert validate_ticket(ticket).valid is True


def test_deterministic_fallback_ticket_invalid_for_live():
    ticket = {**valid_ticket("ABCD"), "deterministic_fallback_executable_allowed": True}
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "deterministic_fallback_not_executable" in result.blockers


def test_grok_authorizer_ticket_invalid_for_live():
    ticket = {**valid_ticket("ABCD"), "authorizer": "grok_d_research"}
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "ticket_authorizer_not_allowed_for_live" in result.blockers


def test_missing_authorizer_ticket_invalid_for_live():
    ticket = valid_ticket("ABCD")
    ticket.pop("authorizer")
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "ticket_authorizer_missing" in result.blockers


def test_expired_ticket_invalid():
    ticket = {**valid_ticket("ABCD"), "expires_at_utc": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "ticket_expired" in result.blockers
