from src.research.trade_authorization_ticket import validate_submission_against_ticket

from tests.test_trade_authorization_ticket import valid_ticket


def test_nvda_failure_replay_blocks_backup_even_when_tape_confirms():
    ticket = {**valid_ticket("INFQ"), "same_style_backup_pool_ok": False}
    ok, reason = validate_submission_against_ticket({"ticker": "NVDA", "mode": "ORB_BREAK"}, ticket, {"status": "GREEN"})
    assert ok is False
    assert reason == "unauthorized_ticker_not_in_deep_research_ticket"


def test_valid_authorized_symbol_can_pass_ticket_gate_in_simulated_path():
    ok, reason = validate_submission_against_ticket({"ticker": "ABCD", "mode": "ORB_BREAK"}, valid_ticket("ABCD"), {"status": "GREEN"})
    assert ok is True
    assert reason is None
