from datetime import datetime, timedelta, timezone

from src.features.opening_tape import OpeningTapeTracker


def test_opening_tape_computes_windows_and_drive_score():
    start = datetime(2026, 5, 21, 13, 30, 0, tzinfo=timezone.utc)
    tape = OpeningTapeTracker("MRAM", premarket_high=10.0, premarket_dollar_volume_per_minute=100_000)
    for i in range(6):
        tape.update_quote(
            {
                "timestamp": (start + timedelta(seconds=i * 2)).isoformat(),
                "bid": 10.02 + i * 0.03,
                "ask": 10.04 + i * 0.03,
                "bid_size": 1000 + i * 100,
                "ask_size": 800,
            }
        )
        tape.update_trade({"timestamp": (start + timedelta(seconds=i * 2)).isoformat(), "price": 10.04 + i * 0.04, "size": 20_000})

    features = tape.features(start + timedelta(seconds=10, milliseconds=500))
    assert features["first_trade_price"] == 10.04
    assert features["window_volume_10s"] == 120_000
    assert features["window_dollar_volume_10s"] > 1_000_000
    assert features["spread_bps"] < 25
    assert features["premarket_high_break_confirmed"] is True
    assert features["micro_vwap_hold"] is True
    assert features["opening_drive_score"] >= 7.0
    assert features["tape_state"] in {"DRIVE_CONFIRMING", "DRIVE_CONFIRMED"}


def test_opening_tape_detects_bid_collapse_and_rug_pull():
    start = datetime(2026, 5, 21, 13, 30, 0, tzinfo=timezone.utc)
    tape = OpeningTapeTracker("RUG", premarket_high=10.0)
    tape.update_quote({"timestamp": start.isoformat(), "bid": 10.0, "ask": 10.05, "bid_size": 5000, "ask_size": 500})
    tape.update_trade({"timestamp": start.isoformat(), "price": 10.0, "size": 10_000})
    tape.update_quote({"timestamp": (start + timedelta(seconds=4)).isoformat(), "bid": 9.65, "ask": 10.2, "bid_size": 200, "ask_size": 6000})
    tape.update_trade({"timestamp": (start + timedelta(seconds=4)).isoformat(), "price": 9.6, "size": 25_000})

    features = tape.features(start + timedelta(seconds=5))
    assert features["bid_collapse_flag"] is True
    assert features["rug_pull_score"] >= 7.0
    assert features["tape_state"] in {"DRIVE_FAILED", "GAP_AND_CRAP", "SPREAD_EXPLODED"}


def test_opening_tape_rejects_crossed_quote_as_invalid_data():
    start = datetime(2026, 5, 21, 13, 30, 0, tzinfo=timezone.utc)
    tape = OpeningTapeTracker("BAD")
    tape.update_quote({"timestamp": start.isoformat(), "bid": 10.1, "ask": 10.0, "bid_size": 1000, "ask_size": 1000})
    tape.update_trade({"timestamp": start.isoformat(), "price": 10.05, "size": 1000})

    features = tape.features(start)
    assert features["spread_regime"] == "MECHANICALLY_IMPOSSIBLE"
    assert features["data_health_score"] == 0.0
    assert features["tape_state"] == "SPREAD_EXPLODED"


def test_opening_tape_keeps_original_opening_anchor_after_trade_retention_trims():
    start = datetime(2026, 5, 21, 13, 30, 0, tzinfo=timezone.utc)
    tape = OpeningTapeTracker("FAST")
    for i in range(2001):
        tape.update_trade({"timestamp": (start + timedelta(milliseconds=i)).isoformat(), "price": 10.0 + (i / 1000), "size": 1})

    features = tape.features(start + timedelta(seconds=2))
    assert features["first_trade_price"] == 10.0
    assert features["regular_open_price"] == 10.0
    assert features["open_5s"] == 10.0
