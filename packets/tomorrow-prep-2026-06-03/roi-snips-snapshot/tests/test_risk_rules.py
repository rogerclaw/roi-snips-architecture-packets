from src.risk.rules import validate_trade_plan


def test_rejects_non_long_direction():
    cfg = {
        "initial_notional_min_usd": 50,
        "initial_notional_max_usd": 100,
        "max_trade_risk_usd": 25,
        "max_spread_bps": 35,
    }
    plan = {
        "ticker": "NVDA",
        "direction": "SHORT",
        "trigger": "ORB_BREAK",
        "entry": 100,
        "stop": 99,
        "target_1": 101,
        "shares": 1,
        "notional_usd": 100,
        "max_risk_usd": 10,
        "spread_bps": 10,
        "max_slippage_bps": 20,
        "open_positions": 0,
    }
    ok, reason = validate_trade_plan(plan, cfg)
    assert not ok
    assert reason == "direction_not_long"


def test_accepts_minimal_valid_plan():
    cfg = {
        "initial_notional_min_usd": 50,
        "initial_notional_max_usd": 100,
        "max_trade_risk_usd": 25,
        "max_spread_bps": 35,
    }
    plan = {
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100,
        "stop": 99.5,
        "target_1": 101,
        "shares": 1,
        "notional_usd": 75,
        "max_risk_usd": 10,
        "spread_bps": 10,
        "max_slippage_bps": 20,
        "open_positions": 0,
    }
    ok, reason = validate_trade_plan(plan, cfg)
    assert ok
    assert reason == "ok"


def test_rejects_extended_hours_plan():
    cfg = {
        "initial_notional_min_usd": 50,
        "initial_notional_max_usd": 100,
        "max_trade_risk_usd": 25,
        "max_spread_bps": 35,
        "max_slippage_bps": 20,
    }
    plan = {
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100,
        "stop": 99.5,
        "target_1": 101,
        "shares": 1,
        "notional_usd": 75,
        "max_risk_usd": 10,
        "spread_bps": 10,
        "max_slippage_bps": 20,
        "open_positions": 0,
        "extended_hours": True,
    }
    ok, reason = validate_trade_plan(plan, cfg)
    assert not ok
    assert reason == "extended_hours_not_allowed"


def test_accepts_valid_opening_drive_plan():
    cfg = {
        "initial_notional_min_usd": 50,
        "initial_notional_max_usd": 1000,
        "max_trade_risk_usd": 80,
        "max_spread_bps": 60,
        "max_slippage_bps": 30,
        "opening_drive_max_spread_bps": 35,
        "opening_drive_max_slippage_bps": 18,
        "opening_drive_max_trade_risk_usd": 40,
        "opening_drive_notional_usd_max": 500,
        "opening_drive_min_first_minute_volume": 150000,
        "opening_drive_min_first_minute_dollar_volume": 750000,
        "opening_drive_max_chase_pct": 1.0,
        "opening_drive_min_close_in_range_pct": 0.6,
    }
    plan = {
        "ticker": "MRAM",
        "direction": "LONG",
        "trigger": "OPENING_DRIVE_LONG",
        "mode": "OPENING_DRIVE_LONG",
        "entry": 10.1,
        "stop": 9.8,
        "target_1": 10.7,
        "shares": 20,
        "notional_usd": 202,
        "max_risk_usd": 6,
        "spread_bps": 20,
        "max_slippage_bps": 15,
        "open_positions": 0,
        "hard_max_entry_price": 10.1,
        "opening_drive_reference_price": 10.0,
        "first_minute_volume": 200000,
        "first_minute_dollar_volume": 2000000,
        "close_in_range_pct": 0.8,
    }
    ok, reason = validate_trade_plan(plan, cfg)
    assert ok
    assert reason == "ok"


def test_rejects_opening_drive_when_chase_limit_exceeded():
    cfg = {
        "initial_notional_min_usd": 50,
        "initial_notional_max_usd": 1000,
        "max_trade_risk_usd": 80,
        "max_spread_bps": 60,
        "max_slippage_bps": 30,
        "opening_drive_max_spread_bps": 35,
        "opening_drive_max_slippage_bps": 18,
        "opening_drive_max_trade_risk_usd": 40,
        "opening_drive_notional_usd_max": 500,
        "opening_drive_min_first_minute_volume": 150000,
        "opening_drive_min_first_minute_dollar_volume": 750000,
        "opening_drive_max_chase_pct": 1.0,
        "opening_drive_min_close_in_range_pct": 0.6,
    }
    plan = {
        "ticker": "MRAM",
        "direction": "LONG",
        "trigger": "OPENING_DRIVE_LONG",
        "mode": "OPENING_DRIVE_LONG",
        "entry": 10.3,
        "stop": 9.9,
        "target_1": 11.0,
        "shares": 10,
        "notional_usd": 103,
        "max_risk_usd": 4,
        "spread_bps": 20,
        "max_slippage_bps": 15,
        "open_positions": 0,
        "hard_max_entry_price": 10.3,
        "opening_drive_reference_price": 10.0,
        "first_minute_volume": 200000,
        "first_minute_dollar_volume": 2000000,
        "close_in_range_pct": 0.8,
    }
    ok, reason = validate_trade_plan(plan, cfg)
    assert not ok
    assert reason == "opening_drive_chase_limit_exceeded"
