from src.strategy.event_timed_catalyst import evaluate_event_timed_catalyst
from src.strategy.halt_reopen_reaction import evaluate_halt_reopen_reaction


def test_event_timed_catalyst_confirmed_bullish_reaction() -> None:
    signal = evaluate_event_timed_catalyst(
        {"ticker": "ABCD"},
        {"outcome": "BULLISH_CONFIRMED", "minutes_from_event": 4, "primary_source_confirmed": True},
        {"headline_breakout_confirmed": True, "price_above_vwap": True, "spread_bps": 35},
    )

    assert signal["action"] == "BUY_HEADLINE_CONFIRMATION"
    assert signal["mode"] == "EVENT_TIMED_HEADLINE_REACTION"
    assert signal["broker_action"] == "NONE"


def test_event_timed_catalyst_rumor_only_waits() -> None:
    signal = evaluate_event_timed_catalyst(
        {"ticker": "ABCD"},
        {"outcome": "RUMOR_ONLY", "minutes_from_event": 2},
        {"headline_breakout_confirmed": True, "spread_bps": 30},
    )

    assert signal["action"] == "NO_TRADE_WAIT"
    assert "rumor_only" in signal["blockers"]
    assert signal["broker_action"] == "NONE"


def test_event_preposition_starter_before_scheduled_event() -> None:
    signal = evaluate_event_timed_catalyst(
        {"ticker": "ABCD"},
        {"outcome": "NEUTRAL", "minutes_from_event": -20, "scheduled_event": True},
    )

    assert signal["action"] == "BUY_STARTER_SIGNAL"
    assert signal["mode"] == "EVENT_PREPOSITION_STARTER"
    assert signal["broker_action"] == "NONE"


def test_halt_reopen_waits_while_halted() -> None:
    signal = evaluate_halt_reopen_reaction({"ticker": "ABCD"}, {"halt_active": True, "tape_state": "HALT_OR_NO_QUOTE"})

    assert signal["action"] == "WAIT"
    assert "halt_active_or_no_quote" in signal["blockers"]
    assert signal["broker_action"] == "NONE"


def test_halt_reopen_reaction_buy_signal_after_reopen_confirmation() -> None:
    signal = evaluate_halt_reopen_reaction(
        {"ticker": "ABCD"},
        {"halt_reopen": True, "reopen_drive_score": 8.5, "reopen_volume_score": 8.2, "spread_bps": 60, "last": 11.2},
    )

    assert signal["action"] == "BUY_NOW"
    assert signal["mode"] == "HALT_REOPEN_REACTION"
    assert signal["broker_action"] == "NONE"
