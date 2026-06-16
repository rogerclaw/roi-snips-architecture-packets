from src.research.trade_authorization_ticket import validate_submission_against_ticket

from tests.test_trade_authorization_ticket import valid_ticket


def test_backup_ticker_cannot_trade_against_primary_ticket():
    ok, reason = validate_submission_against_ticket({"ticker": "NVDA", "mode": "ORB_BREAK"}, valid_ticket("INFQ"))
    assert ok is False
    assert reason == "unauthorized_ticker_not_in_deep_research_ticket"
