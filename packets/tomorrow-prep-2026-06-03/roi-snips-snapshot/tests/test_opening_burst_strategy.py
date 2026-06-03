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


def _candidate(**kwargs):
    base = {
        "ticker": "MRAM",
        "hyper_trade_score": 8.6,
        "lane_tags": ["VERIFIED_CATALYST_RUNNER"],
        "entry_cap": 10.6,
        "thesis_break": 9.9,
        "target_1": 11.5,
    }
    base.update(kwargs)
    return base


def _tape(**kwargs):
    base = {
        "bid": 10.38,
        "ask": 10.4,
        "quote_age_ms": 100,
        "tape_state": "DRIVE_CONFIRMED",
        "opening_drive_score": 8.8,
        "volume_burst_ratio": 9.0,
        "rug_pull_score": 1.0,
        "upper_wick_fade_score": 1.0,
        "chase_risk_score": 2.0,
        "price_above_open": True,
        "premarket_high_break_confirmed": True,
        "micro_vwap_hold": True,
        "open_execution_confidence": 8.5,
        "spread_bps": 20,
    }
    base.update(kwargs)
    return base


def test_strong_opening_drive_emits_buy_before_0931():
    now = datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc)
    signal = evaluate_opening_burst_signal(_candidate(), _tape(), CFG, now=now)
    assert signal["action"] == "BUY_NOW"
    assert signal["trigger"] == "OPENING_BURST_HYPER_LONG"
    assert signal["limit_price"] <= 10.6


def test_instant_dump_emits_no_trade():
    now = datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc)
    signal = evaluate_opening_burst_signal(_candidate(), _tape(tape_state="GAP_AND_CRAP", rug_pull_score=9.0), CFG, now=now)
    assert signal["action"] == "NO_TRADE"
    assert signal["reason"] == "hard_block"


def test_wide_but_tradeable_spread_reduces_size_instead_of_blocking():
    now = datetime(2026, 5, 21, 13, 30, 45, tzinfo=timezone.utc)
    signal = evaluate_opening_burst_signal(_candidate(lane_tags=["SOCIAL_TAPE_ROCKET"], hyper_trade_score=8.2), _tape(spread_bps=150, ask=10.4), CFG, now=now)
    assert signal["action"] == "BUY_NOW"
    assert signal["notional_usd"] <= 300


def test_missing_bid_ask_hard_blocks():
    now = datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc)
    signal = evaluate_opening_burst_signal(_candidate(), _tape(bid=None), CFG, now=now)
    assert signal["action"] == "NO_TRADE"
    assert "missing_bid_ask" in signal["hard_blockers"]


def test_invalid_non_numeric_ask_hard_blocks_instead_of_synthesizing_limit():
    now = datetime(2026, 5, 21, 13, 30, 20, tzinfo=timezone.utc)
    signal = evaluate_opening_burst_signal(_candidate(), _tape(ask="not-a-number"), CFG, now=now)
    assert signal["action"] == "NO_TRADE"
    assert "missing_bid_ask" in signal["hard_blockers"]
