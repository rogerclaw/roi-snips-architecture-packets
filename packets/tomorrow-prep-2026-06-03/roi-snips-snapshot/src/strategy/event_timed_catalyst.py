from __future__ import annotations

from typing import Any


BULLISH_OUTCOMES = {"BULLISH_CONFIRMED", "GUIDANCE_RAISE", "CONTRACT_AWARD", "FDA_APPROVAL"}
NEGATIVE_OUTCOMES = {"DISAPPOINTING", "NO_UPDATE", "RUMOR_ONLY"}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_event_timed_catalyst(candidate: dict[str, Any], event: dict[str, Any], tape: dict[str, Any] | None = None) -> dict[str, Any]:
    tape = tape or {}
    outcome = str(event.get("outcome") or "NEUTRAL").upper()
    minutes = _f(event.get("minutes_from_event"), 999.0)
    spread_bps = _f(tape.get("spread_bps"), 9999.0)
    confirmation = bool(event.get("primary_source_confirmed") or event.get("structured_confirmation"))
    price_confirmed = bool(tape.get("headline_breakout_confirmed") or tape.get("price_above_vwap"))

    blockers: list[str] = []
    if minutes < 0:
        mode = "EVENT_PREPOSITION_STARTER"
        action = "WAIT" if not event.get("scheduled_event") else "BUY_STARTER_SIGNAL"
    elif outcome in BULLISH_OUTCOMES and confirmation and price_confirmed and spread_bps <= 90:
        mode = "EVENT_TIMED_HEADLINE_REACTION"
        action = "BUY_HEADLINE_CONFIRMATION"
    elif outcome in BULLISH_OUTCOMES and confirmation:
        mode = "NEWS_RELEASE_SCALP"
        action = "BUY_BREAKOUT_AFTER_EVENT"
        blockers.append("awaiting_price_confirmation")
    elif outcome == "RUMOR_ONLY":
        mode = "EVENT_TIMED_HEADLINE_REACTION"
        action = "NO_TRADE_WAIT"
        blockers.append("rumor_only")
    elif outcome in NEGATIVE_OUTCOMES:
        mode = "EVENT_TIMED_HEADLINE_REACTION"
        action = "EXIT_OR_REDUCE_STARTER"
        blockers.append(outcome.lower())
    else:
        mode = "EVENT_TIMED_HEADLINE_REACTION"
        action = "NO_TRADE_WAIT"
        blockers.append("neutral_or_unconfirmed_event")

    return {
        "action": action,
        "mode": mode,
        "broker_action": "NONE",
        "order_type": "AGGRESSIVE_LIMIT_ONLY" if action.startswith("BUY") else "NONE",
        "event_outcome": outcome,
        "blockers": blockers,
        "ticker": candidate.get("ticker") or candidate.get("symbol"),
    }
