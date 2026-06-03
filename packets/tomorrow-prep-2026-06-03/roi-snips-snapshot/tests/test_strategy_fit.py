from src.research.strategy_fit import evaluate_strategy_fit


def test_mega_cap_filler_cannot_masquerade_as_a_tier() -> None:
    result = evaluate_strategy_fit(
        {"ticker": "NVDA", "market_cap_bucket": "mega", "asymmetry_score": 4, "freshness_score": 9, "momentum_score": 9}
    )

    assert result.status == "DEGRADED"
    assert "mega_cap_filler_not_a_tier" in result.blockers


def test_full_runbook_mega_cap_default_list_is_blocked() -> None:
    for ticker in ["AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"]:
        result = evaluate_strategy_fit({"ticker": ticker, "asymmetry_score": 4, "freshness_score": 9, "momentum_score": 9})
        assert "mega_cap_filler_not_a_tier" in result.blockers


def test_session_aware_buyability_blocks_premarket_buy_now() -> None:
    result = evaluate_strategy_fit(
        {"ticker": "ABCD", "asymmetry_score": 9, "freshness_score": 9, "momentum_score": 9, "buyability": "BUY_NOW"},
        {"window": "premarket"},
    )

    assert result.buyable_now is False
    assert "premarket_buy_now_not_allowed" in result.blockers
