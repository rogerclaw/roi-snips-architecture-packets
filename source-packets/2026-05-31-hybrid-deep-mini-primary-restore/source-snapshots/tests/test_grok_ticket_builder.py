from src.research.grok_d_research import run_grok_d_research_tournament, run_grok_red_team
from src.research.grok_ticket_builder import create_grok_trade_authorization_ticket
from src.research.trade_authorization_ticket import validate_submission_against_ticket


def _authorized_tournament(ticker="ABCD"):
    return {
        "decision": "AUTHORIZE_ONE",
        "research_leader": ticker,
        "authorized_candidate": {
            "ticker": ticker,
            "strategy": "OPENING_BURST_HYPER_LONG",
            "evidence_split": {
                "official": ["https://ir.example.com/news"],
                "structured": [],
                "social": ["https://x.com/source/status/1"],
                "market_data": [],
            },
            "must_not_trade_if": ["ticket invalid"],
            "thesis_break": "catalyst disproven",
        },
        "research_only_backups": ["WXYZ"],
    }


def test_grok_ticket_builder_is_research_only_and_not_live_valid():
    ticket = create_grok_trade_authorization_ticket(_authorized_tournament(), {"verdict": "PASS", "should_block_ticket": False}, trading_date="2099-05-30")

    assert ticket["valid"] is False
    assert ticket["authorizer"] == "grok_d_research"
    assert ticket["authorized_ticker"] is None
    assert ticket["research_recommended_ticker"] == "ABCD"
    assert ticket["can_authorize_live_trade"] is False
    assert "grok_research_only_not_live_authorizer" in ticket["blockers"]
    assert ticket["backup_execution_allowed"] is False
    assert ticket["backup_tickers_authorized_for_live"] == []
    assert ticket["backups_research_only"] == ["WXYZ"]


def test_grok_ticket_builder_blocks_mega_cap_without_exception():
    ticket = create_grok_trade_authorization_ticket(_authorized_tournament("NVDA"), {"verdict": "PASS", "should_block_ticket": False}, trading_date="2099-05-30")

    assert ticket["valid"] is False
    assert "mega_cap_backup_not_authorized" in ticket["blockers"]


def test_unparsed_or_no_trade_grok_output_creates_no_trade_ticket():
    ticket = create_grok_trade_authorization_ticket({"decision": "NO_TRADE", "no_trade_reason": "structured_output_unparsed"}, {}, trading_date="2099-05-30")

    assert ticket["valid"] is False
    assert ticket["status"] == "NO_TRADE"
    assert ticket["authorized_ticker"] is None


def test_grok_ticket_still_blocks_unauthorized_symbol():
    ticket = create_grok_trade_authorization_ticket(_authorized_tournament("ABCD"), {"verdict": "PASS", "should_block_ticket": False}, trading_date="2099-05-30")

    ok, reason = validate_submission_against_ticket({"ticker": "NVDA", "mode": "OPENING_BURST_HYPER_LONG"}, ticket, {"status": "GREEN"})
    assert ok is False
    assert reason in {
        "deep_research_required_for_live_not_completed",
        "grok_research_only_not_live_authorizer",
        "ticket_authorizer_not_allowed_for_live",
    }
