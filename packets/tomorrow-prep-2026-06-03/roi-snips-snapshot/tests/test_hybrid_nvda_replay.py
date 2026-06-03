from src.research.trade_authorization_ticket import validate_submission_against_ticket


def _deep_mini_ticket(ticker):
    return {
        "status": "AUTHORIZED",
        "authorizer": "openai_deep_mini",
        "authorized_ticker": ticker,
        "authorized_strategy": "ORB_BREAK",
        "completed_before_deadline": True,
        "deep_research_completed": True,
        "deep_research_artifacts": {"final_packet": "runs/2099-05-30/deep_mini/final_packet.json"},
        "deterministic_fallback_executable_allowed": False,
        "backup_execution_allowed": False,
        "exceptional_mega_cap_test_passed": ticker == "NVDA",
    }


def test_grok_nvda_heat_loses_when_deep_mini_authorizes_infq():
    ok, reason = validate_submission_against_ticket({"ticker": "NVDA", "mode": "ORB_BREAK"}, _deep_mini_ticket("INFQ"), {"status": "GREEN"})
    assert ok is False
    assert reason == "unauthorized_ticker_not_in_deep_research_ticket"


def test_grok_discovered_name_can_trade_after_deep_mini_authorizes_it():
    ok, reason = validate_submission_against_ticket({"ticker": "ABCD", "mode": "ORB_BREAK"}, _deep_mini_ticket("ABCD"), {"status": "GREEN"})
    assert ok is True
    assert reason is None
