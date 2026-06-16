from src.ops.artifact_gate import evaluate_artifact_gate
from src.workflows.continuation_monitor import build_continuation_monitor
from src.workflows.event_catalyst_monitor import build_event_catalyst_monitor
from src.workflows.post_miss_audit import build_post_miss_audit, build_slice5_artifacts


def _base_gate_artifacts() -> dict:
    return {
        "morning_control_plane": {"brokerless_shadow_only": True},
        "broad_discovery": {"candidate_count": 3},
        "research_war_room": {"status": "OK"},
        "candidate_tournament": {
            "best_pick": "ABCD",
            "stale_winner_blocked": True,
            "mega_cap_fallback_blocked": True,
        },
        "catalyst_strategy_router": {"allowed_modes": ["OPENING_BURST_HYPER_LONG"], "broker_action": "NONE"},
        "opening_bell_engine": {"broker_action": "NONE"},
        "execution_plan": {"broker_action": "NONE"},
        "no_order_attestation": {"brokerless": True, "orders_submitted": False},
    }


def test_continuation_monitor_outputs_artifact_gate_continuation_engine() -> None:
    result = build_continuation_monitor(
        {"ticker": "ABCD", "premarket_high": 10.4},
        [
            {"close": 10.0, "low": 9.9, "high": 10.1, "volume": 1000, "vwap": 10.0},
            {"close": 10.2, "low": 10.0, "high": 10.25, "volume": 1200, "vwap": 10.1},
            {"close": 10.1, "low": 10.02, "high": 10.22, "volume": 1300, "vwap": 10.12},
            {"close": 10.25, "low": 10.1, "high": 10.3, "volume": 1400, "vwap": 10.18},
            {"close": 10.18, "low": 10.08, "high": 10.28, "volume": 1500, "vwap": 10.22},
            {"close": 10.55, "low": 10.3, "high": 10.6, "volume": 2600, "vwap": 10.3},
        ],
        {"spread_bps": 35, "opening_range_high": 10.4, "opening_range_low": 9.9},
    )

    payload = result.to_dict()
    assert payload["broker_action"] == "NONE"
    assert payload["orders_submitted"] is False
    assert payload["continuation_engine"]["broker_action"] == "NONE"
    assert payload["continuation_engine"]["buy_signal_count"] >= 1


def test_event_catalyst_monitor_outputs_event_engine_without_orders() -> None:
    result = build_event_catalyst_monitor(
        {"ticker": "ABCD"},
        [{"outcome": "BULLISH_CONFIRMED", "minutes_from_event": 2, "primary_source_confirmed": True}],
        {"headline_breakout_confirmed": True, "price_above_vwap": True, "spread_bps": 35},
    )

    payload = result.to_dict()
    assert payload["status"] == "SIGNAL_READY"
    assert payload["broker_action"] == "NONE"
    assert payload["orders_submitted"] is False
    assert payload["event_timed_engine"]["headline_reaction"] is True
    assert payload["event_timed_engine"]["broker_action"] == "NONE"


def test_post_miss_audit_records_source_ranking_execution_and_prompt_failures() -> None:
    audit = build_post_miss_audit(
        source_lane_status=[
            {"lane_name": "Benzinga", "ran": False, "configured": True},
            {"lane_name": "Grok/X", "ran": True, "errors": ["rate_limited"]},
        ],
        ranking_report={
            "best_pick": None,
            "stale_winner_blocked": False,
            "mega_cap_fallback_blocked": False,
            "failures": [{"reason": "thin_universe"}],
        },
        execution_report={
            "stream_missing": True,
            "opening_burst_window_not_covered": True,
            "no_exit_manager": True,
            "broker_action": "NONE",
            "failures": [{"reason": "spread_exploded"}],
        },
        prompt_report={"missing_fields": ["buy_zone", "danger_signals"], "failures": [{"field": "thesis_break"}]},
        missed_symbol="RUNR",
    )

    payload = audit.to_dict()
    assert payload["status"] == "RECORDED"
    assert payload["broker_action"] == "NONE"
    assert "Benzinga" in payload["source_lane_failures"]
    assert "Grok/X" in payload["source_lane_failures"]
    assert "missing_best_pick" in payload["ranking_failures"]
    assert "stale_winner_not_blocked" in payload["ranking_failures"]
    assert "stream_missing" in payload["execution_failures"]
    assert "no_exit_manager" in payload["execution_failures"]
    assert "missing_prompt_field:buy_zone" in payload["prompt_failures"]
    assert payload["post_miss_learning"]["records_source_lane_failures"] is True
    assert payload["post_miss_learning"]["records_ranking_failures"] is True
    assert payload["post_miss_learning"]["records_execution_failures"] is True
    assert payload["post_miss_learning"]["records_prompt_failures"] is True


def test_slice5_outputs_feed_artifact_gate() -> None:
    continuation = build_continuation_monitor(
        {"ticker": "ABCD", "premarket_high": 10.4},
        [
            {"close": 10.0, "low": 9.9, "high": 10.1, "volume": 1000, "vwap": 10.0},
            {"close": 10.2, "low": 10.0, "high": 10.25, "volume": 1200, "vwap": 10.1},
            {"close": 10.1, "low": 10.02, "high": 10.22, "volume": 1300, "vwap": 10.12},
            {"close": 10.25, "low": 10.1, "high": 10.3, "volume": 1400, "vwap": 10.18},
            {"close": 10.18, "low": 10.08, "high": 10.28, "volume": 1500, "vwap": 10.22},
            {"close": 10.55, "low": 10.3, "high": 10.6, "volume": 2600, "vwap": 10.3},
        ],
        {"spread_bps": 35, "opening_range_high": 10.4, "opening_range_low": 9.9},
    ).to_dict()
    event = build_event_catalyst_monitor(
        {"ticker": "ABCD"},
        [{"outcome": "BULLISH_CONFIRMED", "minutes_from_event": 2, "primary_source_confirmed": True}],
        {"headline_breakout_confirmed": True, "price_above_vwap": True, "spread_bps": 35},
    ).to_dict()
    post_miss = build_post_miss_audit().to_dict()
    artifacts = _base_gate_artifacts()
    artifacts.update(build_slice5_artifacts(continuation_result=continuation, event_result=event, post_miss_result=post_miss))

    gate = evaluate_artifact_gate(artifacts)

    assert gate.ready is True
    assert gate.blockers == []
    assert gate.no_order_attestation is True
