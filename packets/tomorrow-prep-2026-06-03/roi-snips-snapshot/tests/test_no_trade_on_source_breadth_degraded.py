from src.research.deep_research_trade_authorization import create_trade_authorization_ticket_from_deep_research


def test_source_breadth_degraded_without_explicit_authorized_ticker_is_no_trade():
    ticket = create_trade_authorization_ticket_from_deep_research(
        {
            "trade_authorization": {"authorized_for_live_consideration": False, "ticker": None},
            "source_breadth_status": "DEGRADED_LOW_RAW_CANDIDATE_COUNT",
        },
        trading_date="2026-05-29",
        completed_before_deadline=True,
    )
    assert ticket["valid"] is False
    assert ticket["status"] == "NO_TRADE"
