from src.research.strategy_fit import evaluate_strategy_fit


def test_premarket_window_requires_wait_for_relevant_window() -> None:
    result = evaluate_strategy_fit(
        {"ticker": "WXYZ", "asymmetry_score": 8.5, "freshness_score": 8.5, "momentum_score": 8.5, "buyability": "market_open_only"},
        {"market_session": "premarket"},
    )

    assert result.buyable_now is False
    assert result.status == "DEGRADED"
