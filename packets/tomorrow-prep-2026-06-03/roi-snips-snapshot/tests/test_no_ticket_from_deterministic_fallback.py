from src.research.deep_research_trade_authorization import create_trade_authorization_ticket_from_deep_research


def test_deterministic_fallback_cannot_create_authorized_live_ticket():
    ticket = create_trade_authorization_ticket_from_deep_research(
        {"best_pick": "ABCD", "source_mode": "internal_fallback", "deterministic_fallback_executable_allowed": True},
        trading_date="2026-05-29",
        completed_before_deadline=True,
    )
    assert ticket["valid"] is False
    assert "deterministic_fallback_not_executable" in ticket["blockers"]
