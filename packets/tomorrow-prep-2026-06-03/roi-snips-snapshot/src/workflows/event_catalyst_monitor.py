from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..strategy.event_timed_catalyst import evaluate_event_timed_catalyst
from ..strategy.halt_reopen_reaction import evaluate_halt_reopen_reaction


@dataclass
class EventCatalystMonitorResult:
    status: str
    symbol: str
    event_timed_engine: dict[str, Any]
    decisions: list[dict[str, Any]] = field(default_factory=list)
    broker_action: str = "NONE"
    orders_submitted: bool = False
    generated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_event_catalyst_monitor(
    candidate: dict[str, Any],
    events: list[dict[str, Any]],
    tape: dict[str, Any] | None = None,
) -> EventCatalystMonitorResult:
    tape = tape or {}
    symbol = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
    decisions: list[dict[str, Any]] = []
    for event in events:
        decisions.append(evaluate_event_timed_catalyst(candidate, event, tape))
        if event.get("halt_reopen") or tape.get("halt_reopen") or tape.get("halt_active"):
            decisions.append(evaluate_halt_reopen_reaction(candidate, {**tape, **event}))

    if not decisions:
        decisions.append({"action": "NO_TRADE_WAIT", "mode": "EVENT_TIMED_HEADLINE_REACTION", "broker_action": "NONE", "blockers": ["no_event_updates"]})

    buy_signals = [row for row in decisions if str(row.get("action", "")).startswith("BUY")]
    status = "SIGNAL_READY" if buy_signals else "WAIT"
    engine = {
        "engine": "event_catalyst_monitor",
        "status": status,
        "broker_action": "NONE",
        "orders_submitted": False,
        "headline_reaction": any(row.get("mode") == "EVENT_TIMED_HEADLINE_REACTION" for row in decisions),
        "event_preposition_starter": any(row.get("mode") == "EVENT_PREPOSITION_STARTER" for row in decisions),
        "news_release_scalp": any(row.get("mode") == "NEWS_RELEASE_SCALP" for row in decisions),
        "halt_reopen_reaction": any(row.get("mode") == "HALT_REOPEN_REACTION" for row in decisions),
        "buy_signal_count": len(buy_signals),
    }
    return EventCatalystMonitorResult(status=status, symbol=symbol, event_timed_engine=engine, decisions=decisions)
