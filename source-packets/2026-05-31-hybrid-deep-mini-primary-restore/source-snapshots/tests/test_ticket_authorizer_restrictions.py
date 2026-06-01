from src.research.trade_authorization_ticket import validate_ticket


def _ticket(authorizer):
    return {
        "status": "AUTHORIZED",
        "authorizer": authorizer,
        "authorized_ticker": "ABCD",
        "authorized_strategy": "ORB_BREAK",
        "completed_before_deadline": True,
        "deep_research_completed": True,
        "deep_research_artifacts": {"final_packet": "runs/2099-05-30/deep_mini/final_packet.json"},
        "deterministic_fallback_executable_allowed": False,
        "backup_execution_allowed": False,
    }


def test_openai_deep_mini_authorizer_allowed():
    assert validate_ticket(_ticket("openai_deep_mini")).valid is True


def test_governed_deep_research_authorizer_allowed():
    assert validate_ticket(_ticket("governed_deep_research")).valid is True


def test_social_and_deterministic_authorizers_blocked():
    for authorizer in ["grok_d_research", "grok_x_heat_radar", "deterministic_fallback", "social_only"]:
        result = validate_ticket(_ticket(authorizer))
        assert result.valid is False
        assert "ticket_authorizer_not_allowed_for_live" in result.blockers


def test_no_trade_ticket_blocks_live():
    ticket = {**_ticket("openai_deep_mini"), "status": "NO_TRADE", "authorized_ticker": None}
    result = validate_ticket(ticket)
    assert result.valid is False
    assert "ticket_no_trade" in result.blockers
