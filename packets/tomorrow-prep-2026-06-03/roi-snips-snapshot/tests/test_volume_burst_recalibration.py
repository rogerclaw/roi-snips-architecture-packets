from datetime import datetime, timedelta, timezone

from src.features.opening_tape import OpeningTapeTracker


def test_volume_burst_components_include_absolute_and_continuation_scores() -> None:
    tracker = OpeningTapeTracker("INFQ", expected_opening_dollar_volume_60s=50_000, premarket_high=12.0)
    start = datetime(2026, 5, 27, 13, 30, tzinfo=timezone.utc)
    for idx in range(8):
        ts = start + timedelta(seconds=idx * 5)
        tracker.update_quote({"timestamp": ts.isoformat(), "bid": 12.0 + idx * 0.01, "ask": 12.02 + idx * 0.01, "bid_size": 1000, "ask_size": 800})
        tracker.update_trade({"timestamp": ts.isoformat(), "price": 12.03 + idx * 0.02, "size": 2000})

    features = tracker.features(start + timedelta(seconds=45))

    assert features["volume_burst_ratio"] > 0
    assert "absolute_dollar_volume" in features["volume_burst_components"]
    assert "continuation_volume_expansion" in features["volume_burst_components"]
    assert "volume_quality_after_reset" in features["volume_burst_components"]
