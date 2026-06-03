from src.execution.fast_cancel import should_fast_cancel
from src.execution.opening_position_manager import opening_position_action


def test_fast_cancel_on_weak_unfilled_order():
    cancel, reason = should_fast_cancel({"status": "new", "elapsed_seconds": 3, "cancel_after_seconds": 2, "entry_cap": 10.5}, {"opening_drive_score": 4.5, "latest_price": 10.4}, {})
    assert cancel is True
    assert reason == "unfilled_and_tape_weak"


def test_fast_cancel_respects_entry_cap():
    cancel, reason = should_fast_cancel({"status": "new", "elapsed_seconds": 1, "entry_cap": 10.5}, {"opening_drive_score": 9.0, "latest_price": 10.7}, {})
    assert cancel is True
    assert reason == "price_above_entry_cap_before_fill"


def test_fast_cancel_on_spread_bid_and_stale_stream_failures():
    for tape, expected in [
        ({"tape_state": "SPREAD_EXPLODED"}, "spread_exploded"),
        ({"bid_collapse_flag": True}, "bid_collapse"),
        ({"tape_state": "STALE_DATA"}, "stale_data"),
        ({"tape_state": "DRIVE_FAILED"}, "drive_failed"),
    ]:
        cancel, reason = should_fast_cancel({"status": "new", "elapsed_seconds": 1, "entry_cap": 10.5}, tape, {})
        assert cancel is True
        assert reason == expected


def test_opening_position_manager_exits_on_thesis_break():
    action = opening_position_action({"qty": 10, "entry_price": 10.0, "thesis_break": 9.7}, {"latest_price": 9.65, "tape_state": "DRIVE_FAILED"}, {"opening_bell": {"exits": {"time_stop_seconds_soft": 120}}})
    assert action["action"] == "EXIT"
    assert action["reason"] in {"thesis_break", "drive_failed"}


def test_fast_cancel_handles_malformed_numeric_fields_without_crashing():
    cancel, reason = should_fast_cancel(
        {"status": "new", "elapsed_seconds": "bad", "cancel_after_seconds": "bad", "entry_cap": "bad", "replace_count": "bad"},
        {"opening_drive_score": "bad", "latest_price": "bad"},
        {},
    )
    assert cancel is True
    assert reason == "malformed_numeric_input"
