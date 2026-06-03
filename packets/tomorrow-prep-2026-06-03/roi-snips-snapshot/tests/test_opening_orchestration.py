from datetime import datetime
from zoneinfo import ZoneInfo

from src.strategy.opening_burst_hyper_long import evaluate_opening_burst_signal


def test_opening_orchestration_waits_then_hands_off_after_burst_window() -> None:
    cfg = {"opening_bell": {"thresholds": {"first_30s": {"min_hyper_trade_score": 7, "min_opening_drive_score": 7, "min_volume_burst_score": 6}}, "data": {"max_quote_age_ms": 1000}}}
    candidate = {"ticker": "INFQ", "hyper_trade_score": 9, "entry_cap": 12.5, "lane_tags": ["VERIFIED_CATALYST_RUNNER"]}
    tape = {"bid": 12.0, "ask": 12.02, "quote_age_ms": 10, "tape_state": "DRIVE_CONFIRMED"}

    observe = evaluate_opening_burst_signal(candidate, tape, cfg, now=datetime(2026, 5, 27, 9, 30, 2, tzinfo=ZoneInfo("America/New_York")))
    closed = evaluate_opening_burst_signal(candidate, tape, cfg, now=datetime(2026, 5, 27, 9, 35, 1, tzinfo=ZoneInfo("America/New_York")))

    assert observe["reason"] == "first_print_observe_window"
    assert "continuation_handoff_required" in closed["failed_predicates"]
