from src.strategy.orb_breakout import evaluate_orb_breakout
from src.strategy.premarket_high_reclaim import evaluate_premarket_high_reclaim
from src.strategy.second_leg_continuation import evaluate_second_leg_continuation
from src.strategy.vwap_washout_reclaim import evaluate_vwap_washout_reclaim


def test_second_leg_continuation_trigger() -> None:
    signal = evaluate_second_leg_continuation(
        symbol="ABCD",
        closes=[10.0, 10.2, 10.1, 10.25, 10.18, 10.55],
        lows=[9.9, 10.0, 10.02, 10.1, 10.08, 10.3],
        highs=[10.1, 10.25, 10.22, 10.3, 10.28, 10.6],
        volumes=[1000, 1200, 1300, 1400, 1500, 2600],
        vwaps=[10.0, 10.1, 10.12, 10.18, 10.22, 10.3],
        spread_bps=35,
        opening_range_high=10.4,
        opening_range_low=9.9,
    )

    assert signal["action"] == "BUY_NOW"
    assert signal["mode"] in {"ORB_BREAK_LONG", "SECOND_LEG_CONTINUATION_LONG", "VWAP_RECLAIM_LONG"}


def test_premarket_high_reclaim_engine() -> None:
    signal = evaluate_premarket_high_reclaim(
        {"ticker": "ABCD", "premarket_high": 10.4},
        {"last": 10.52, "premarket_high_reclaim_confirmed": True, "volume_burst_ratio": 8.0, "spread_bps": 40},
    )

    assert signal["action"] == "BUY_NOW"
    assert signal["mode"] == "PREMARKET_HIGH_RECLAIM"
    assert signal["broker_action"] == "NONE"


def test_vwap_washout_reclaim_engine() -> None:
    signal = evaluate_vwap_washout_reclaim(
        {"ticker": "ABCD"},
        {
            "last": 10.45,
            "vwap": 10.25,
            "vwap_washout_seen": True,
            "higher_low_confirmed": True,
            "volume_burst_ratio": 7.5,
            "spread_bps": 45,
        },
    )

    assert signal["action"] == "BUY_NOW"
    assert signal["mode"] == "VWAP_WASHOUT_RECLAIM"
    assert signal["broker_action"] == "NONE"


def test_orb_breakout_engine_supports_one_and_five_minute_modes() -> None:
    tape = {"last": 10.75, "opening_range_high": 10.5, "opening_range_low": 10.0, "volume_burst_ratio": 8.0, "spread_bps": 40}

    one = evaluate_orb_breakout({"ticker": "ABCD"}, tape, minutes=1)
    five = evaluate_orb_breakout({"ticker": "ABCD"}, tape, minutes=5)

    assert one["action"] == "BUY_NOW"
    assert one["mode"] == "ORB_BREAK_1MIN"
    assert five["action"] == "BUY_NOW"
    assert five["mode"] == "ORB_BREAK_5MIN"
