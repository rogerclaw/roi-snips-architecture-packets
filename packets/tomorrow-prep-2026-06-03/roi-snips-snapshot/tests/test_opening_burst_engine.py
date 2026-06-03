from datetime import datetime, timezone

from src.strategy.opening_burst_hyper_long import evaluate_opening_burst_signal


CFG = {
    "opening_bell": {
        "data": {"max_quote_age_ms": 1000},
        "thresholds": {
            "first_10s": {"min_hyper_trade_score": 8.0, "min_opening_drive_score": 8.5, "min_volume_burst_score": 8.0, "max_rug_pull_score": 3.0, "max_upper_wick_fade_score": 4.0},
            "first_30s": {"min_hyper_trade_score": 7.5, "min_opening_drive_score": 7.8, "min_volume_burst_score": 7.0, "max_rug_pull_score": 4.0, "max_upper_wick_fade_score": 5.0},
            "first_60s": {"min_hyper_trade_score": 7.0, "min_opening_drive_score": 7.2, "min_volume_burst_score": 6.5, "max_rug_pull_score": 5.0, "max_chase_risk_score": 6.0},
        },
        "order": {"slippage_cap_bps": 20, "slippage_cap_cents": 0.03},
        "sizing": {"verified_default_usd": 300, "verified_strong_usd": 500, "social_tape_default_usd": 100, "social_tape_max_usd": 300, "a_plus_max_usd": 1000},
    }
}


def _candidate() -> dict:
    return {"ticker": "ABCD", "hyper_trade_score": 8.8, "lane_tags": ["VERIFIED_CATALYST_RUNNER"], "entry_cap": 10.75}


def _tape(**overrides) -> dict:
    tape = {
        "bid": 10.48,
        "ask": 10.5,
        "quote_age_ms": 100,
        "tape_state": "DRIVE_CONFIRMED",
        "opening_drive_score": 8.9,
        "volume_burst_ratio": 9.0,
        "rug_pull_score": 1.0,
        "upper_wick_fade_score": 1.0,
        "chase_risk_score": 2.0,
        "price_above_open": True,
        "premarket_high_break_confirmed": True,
        "micro_vwap_hold": True,
        "spread_bps": 20,
    }
    tape.update(overrides)
    return tape


def test_opening_burst_buy_now_synthetic_tape() -> None:
    signal = evaluate_opening_burst_signal(_candidate(), _tape(), CFG, now=datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc))

    assert signal["action"] == "BUY_NOW"
    assert signal["mode"] == "OPENING_BURST_HYPER_LONG"
    assert signal["limit_price"] <= 10.75


def test_opening_burst_no_trade_on_upper_wick_failure() -> None:
    signal = evaluate_opening_burst_signal(
        _candidate(),
        _tape(upper_wick_fade_score=9.0),
        CFG,
        now=datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc),
    )

    assert signal["action"] == "NO_TRADE"
    assert "upper_wick_risk_ok" in signal["failed_predicates"]


def test_opening_burst_no_trade_on_bid_collapse() -> None:
    signal = evaluate_opening_burst_signal(
        _candidate(),
        _tape(bid_collapse_flag=True),
        CFG,
        now=datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc),
    )

    assert signal["action"] == "NO_TRADE"
    assert "bid_collapse" in signal["hard_blockers"]


def test_opening_burst_no_trade_on_spread_explosion() -> None:
    signal = evaluate_opening_burst_signal(
        _candidate(),
        _tape(tape_state="SPREAD_EXPLODED"),
        CFG,
        now=datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc),
    )

    assert signal["action"] == "NO_TRADE"
    assert "spread_exploded" in signal["hard_blockers"]
