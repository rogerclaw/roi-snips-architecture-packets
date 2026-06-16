from src.research.trade_authorization_ticket import validate_submission_against_ticket

from tests.test_trade_authorization_ticket import valid_ticket


def test_same_style_backup_failure_does_not_authorize_backup_execution():
    ticket = {**valid_ticket("INFQ"), "same_style_backup_pool_ok": False}
    ok, reason = validate_submission_against_ticket({"ticker": "NVDA", "mode": "ORB_BREAK"}, ticket)
    assert ok is False
    assert reason == "unauthorized_ticker_not_in_deep_research_ticket"
