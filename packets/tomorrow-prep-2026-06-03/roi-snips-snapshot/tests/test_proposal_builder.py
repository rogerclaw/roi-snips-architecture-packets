from src.execution.proposal_builder import build_trade_proposal
import pytest


def test_build_trade_proposal_uses_execution_command_only():
    proposal = build_trade_proposal(
        {
            "ticker": "NVDA",
            "entry": 100.0,
            "stop": 99.0,
            "target_1": 102.0,
            "shares": 1,
            "notional_usd": 100.0,
            "max_risk_usd": 1.0,
            "trigger": "VWAP_RECLAIM",
        }
    )

    assert proposal["execution_command"].startswith("EXECUTE ENTRY ")
    assert "approval_command" not in proposal


def test_build_trade_proposal_rejects_invalid_long_price_geometry():
    with pytest.raises(ValueError, match="stop_must_be_below_entry"):
        build_trade_proposal(
            {
                "ticker": "INFQ",
                "entry": 10.0,
                "stop": 10.1,
                "target_1": 10.5,
                "shares": 1,
                "notional_usd": 10.0,
                "max_risk_usd": 1.0,
                "trigger": "OPENING_BURST_HYPER_LONG",
            }
        )
