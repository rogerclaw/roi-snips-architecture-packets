from src.workflows.live_monitor import _validate_ticket_for_submission

from tests.test_trade_authorization_ticket import valid_ticket


def test_ticket_for_infq_blocks_nvda_even_if_monitor_builds_a_proposal():
    ok, reason = _validate_ticket_for_submission({"ticker": "NVDA", "mode": "ORB_BREAK"}, valid_ticket("INFQ"))
    assert ok is False
    assert reason == "unauthorized_ticker_not_in_deep_research_ticket"


def test_no_trade_ticket_blocks_all_live_monitor_submissions():
    ticket = {**valid_ticket("INFQ"), "status": "NO_TRADE", "authorized_ticker": None}
    ok, reason = _validate_ticket_for_submission({"ticker": "INFQ", "mode": "ORB_BREAK"}, ticket)
    assert ok is False
    assert reason == "ticket_no_trade"
