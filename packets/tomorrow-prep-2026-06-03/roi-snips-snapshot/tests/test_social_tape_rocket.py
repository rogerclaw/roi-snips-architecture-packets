from src.strategy.social_tape_rocket import evaluate_social_tape_rocket


def _candidate(**kwargs):
    base = {
        "ticker": "INFQ",
        "validation_status": "social_discovery_only",
        "official_confirmation_count": 0,
        "structured_confirmation_count": 0,
        "attention_acceleration_score": 9.0,
        "hyper_trade_score": 8.1,
    }
    base.update(kwargs)
    return base


def _tape(**kwargs):
    base = {
        "opening_drive_score": 8.0,
        "volume_burst_ratio": 8.5,
        "spread_bps": 120,
        "premarket_high_break_confirmed": True,
        "micro_vwap_hold": True,
        "tape_state": "DRIVE_CONFIRMED",
    }
    base.update(kwargs)
    return base


def test_social_tape_rocket_requires_hard_confirmation_even_when_tape_confirms():
    result = evaluate_social_tape_rocket(_candidate(), _tape())
    assert result["action"] == "WAIT"
    assert result["reason"] == "social_discovery_requires_official_or_structured_confirmation"
    assert "official_or_structured_confirmation_present" in result["failed_predicates"]


def test_social_tape_rocket_can_qualify_with_structured_confirmation_and_tape():
    result = evaluate_social_tape_rocket(_candidate(validation_status="structured_confirmed", structured_confirmation_count=1), _tape())
    assert result["action"] == "BUY_NOW"
    assert result["reason"] == "social_tape_rocket_confirmed"
    assert result["failed_predicates"] == []


def test_social_only_text_pump_waits_without_tape_confirmation():
    result = evaluate_social_tape_rocket(_candidate(), _tape(opening_drive_score=2.0, volume_burst_ratio=1.0, premarket_high_break_confirmed=False, micro_vwap_hold=False))
    assert result["action"] == "WAIT"
    assert result["reason"] == "social_discovery_requires_official_or_structured_confirmation"
    assert "tape_confirmation_present" in result["failed_predicates"]
