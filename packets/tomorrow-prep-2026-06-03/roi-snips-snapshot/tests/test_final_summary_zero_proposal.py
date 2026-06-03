from datetime import datetime
from zoneinfo import ZoneInfo

from src.strategy.opening_burst_hyper_long import evaluate_opening_burst_signal


def test_zero_proposal_decision_explains_failed_predicates() -> None:
    decision = evaluate_opening_burst_signal(
        {"ticker": "INFQ", "hyper_trade_score": 9, "entry_cap": 12.5},
        {"bid": 12.0, "ask": 12.02, "quote_age_ms": 10, "opening_drive_score": 3, "volume_burst_ratio": 2, "tape_state": "FIRST_PRINT_SEEN"},
        {"opening_bell": {"thresholds": {"first_30s": {"min_hyper_trade_score": 7, "min_opening_drive_score": 7, "min_volume_burst_score": 6}}, "data": {"max_quote_age_ms": 1000}}},
        now=datetime(2026, 5, 27, 9, 30, 20, tzinfo=ZoneInfo("America/New_York")),
    )

    assert decision["action"] in {"WAIT", "NO_TRADE"}
    assert decision["reason"] == "setup_not_confirmed"
    assert "opening_drive_score_ok" in decision["failed_predicates"]
    assert "volume_burst_ok" in decision["failed_predicates"]
