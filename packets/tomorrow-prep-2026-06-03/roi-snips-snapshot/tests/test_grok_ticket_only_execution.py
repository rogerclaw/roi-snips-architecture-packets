from src.research.grok_ticket_builder import create_grok_trade_authorization_ticket
from src.research.trade_authorization_ticket import ticket_authorizes_symbol, validate_submission_against_ticket


def test_grok_ticket_only_execution_remains_research_only():
    ticket = create_grok_trade_authorization_ticket(
        {
            "decision": "AUTHORIZE_ONE",
            "research_leader": "ABCD",
            "authorized_candidate": {
                "ticker": "ABCD",
                "strategy": "ORB_BREAK",
                "evidence_split": {"official": ["https://ir.example.com"], "structured": [], "social": ["https://x.com/a"], "market_data": []},
            },
            "research_only_backups": ["NVDA"],
        },
        {"verdict": "PASS", "should_block_ticket": False},
        trading_date="2099-05-30",
    )

    assert ticket["valid"] is False
    assert ticket_authorizes_symbol(ticket, "ABCD") is False
    assert ticket_authorizes_symbol(ticket, "NVDA") is False
    ok, reason = validate_submission_against_ticket({"ticker": "NVDA", "mode": "ORB_BREAK"}, ticket, {"status": "GREEN"})
    assert ok is False
    assert reason in {"deep_research_required_for_live_not_completed", "grok_research_only_not_live_authorizer"}
