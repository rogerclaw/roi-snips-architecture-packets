from src.research.deep_research_trade_authorization import create_trade_authorization_ticket_from_deep_research


def test_completed_deep_research_creates_authorized_ticket():
    ticket = create_trade_authorization_ticket_from_deep_research(
        {"trade_authorization": {"authorized_for_live_consideration": True, "ticker": "ABCD", "authorized_strategy": "ORB_BREAK"}},
        trading_date="2099-05-29",
        completed_before_deadline=True,
    )
    assert ticket["valid"] is True
    assert ticket["authorized_ticker"] == "ABCD"


def test_failed_deep_research_creates_no_trade_ticket():
    ticket = create_trade_authorization_ticket_from_deep_research(
        {"trade_authorization": {"authorized_for_live_consideration": False, "ticker": None}},
        trading_date="2099-05-29",
        completed_before_deadline=True,
    )
    assert ticket["valid"] is False
    assert ticket["status"] == "NO_TRADE"
