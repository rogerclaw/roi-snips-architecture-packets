from src.research.grok_ticket_builder import create_grok_ticket_input_summary, create_grok_trade_authorization_ticket
from src.research.trade_authorization_ticket import validate_ticket


def _tournament(ticker="ABCD"):
    return {
        "decision": "RECOMMEND_FOR_DEEP_MINI_REVIEW",
        "authorized_candidate": {"ticker": ticker, "strategy": "OPENING_BURST_HYPER_LONG"},
        "research_only_backups": ["WXYZ"],
    }


def test_grok_ticket_candidate_is_invalid_for_live():
    ticket = create_grok_trade_authorization_ticket(_tournament(), {"should_block_ticket": False}, trading_date="2099-05-30")

    assert ticket["valid"] is False
    assert ticket["can_authorize_live_trade"] is False
    assert ticket["authorized_ticker"] is None
    assert ticket["research_recommended_ticker"] == "ABCD"
    assert "grok_research_only_not_live_authorizer" in validate_ticket(ticket).blockers


def test_grok_ticket_input_summary_is_research_only():
    summary = create_grok_ticket_input_summary(_tournament(), {"should_block_ticket": False}, trading_date="2099-05-30")

    assert summary["grok_research_only"] is True
    assert summary["can_authorize_live_trade"] is False
    assert summary["names_for_deep_mini_to_judge"] == ["ABCD"]
