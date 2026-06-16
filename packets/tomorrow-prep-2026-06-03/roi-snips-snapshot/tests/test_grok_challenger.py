from src.research.grok_challenger import run_grok_challenger


def test_grok_challenger_cannot_authorize_or_switch_ticker():
    result = run_grok_challenger({"authorized_ticker": "INFQ"}, [{"ticker": "NVDA", "mentions": 10}])
    assert result["disagreement"] is True
    assert result["can_authorize_live_trade"] is False
    assert result["executable_primary"] is None
    assert result["recommended_action"] == "RERUN_OR_NO_TRADE_UNTIL_NEW_OPENAI_TICKET"
