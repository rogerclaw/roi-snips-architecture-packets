from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


RUNBOOK_MODES = [
    "OPENING_BURST_HYPER_LONG",
    "GAP_AND_GO_CONFIRMATION",
    "PREMARKET_HIGH_RECLAIM",
    "VWAP_WASHOUT_RECLAIM",
    "ORB_BREAK_1MIN",
    "ORB_BREAK_5MIN",
    "SECOND_LEG_CONTINUATION",
    "EVENT_TIMED_HEADLINE_REACTION",
    "EVENT_PREPOSITION_STARTER",
    "NEWS_RELEASE_SCALP",
    "HALT_REOPEN_REACTION",
    "NO_TRADE_WAIT",
]


@dataclass
class StrategyRoute:
    ticker: str
    allowed_modes: list[str]
    primary_mode: str
    proof_scope: str
    broker_action: str = "NONE"
    order_intent: str = "SIGNAL_ONLY"
    order_type: str = "AGGRESSIVE_LIMIT_ONLY"
    exit_manager_required: bool = True
    exit_manager_present: bool = True
    market_open_ready: bool = True
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _minutes_from_open(tape: dict[str, Any], session: dict[str, Any]) -> float:
    if "minutes_from_open" in tape:
        return _f(tape.get("minutes_from_open"))
    return _f(session.get("minutes_from_open"))


def route_strategy(
    candidate: dict[str, Any],
    tape: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
    *,
    event: dict[str, Any] | None = None,
    has_exit_manager: bool = True,
) -> StrategyRoute:
    """Route runbook strategy modes without touching broker state.

    The router returns strategy eligibility only. Every result is signal-only and
    explicitly forbids broker actions so Slice 4 can be validated in no-order
    mode before any later arming decision.
    """

    tape = tape or {}
    session = session or {}
    event = event or {}
    ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
    minutes = _minutes_from_open(tape, session)
    window = str(session.get("window") or session.get("market_session") or "").lower()
    gap_pct = _f(candidate.get("gap_pct") or tape.get("gap_pct"))
    event_minutes = event.get("minutes_from_event", tape.get("event_minutes"))
    halt_reopen = bool(event.get("halt_reopen") or tape.get("halt_reopen"))

    allowed: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    proof_scope = "MARKET_OPEN_READINESS"
    market_open_ready = True

    if not has_exit_manager:
        blockers.append("missing_exit_manager")

    if window == "premarket" or minutes < 0:
        if candidate.get("premarket_high") or tape.get("premarket_high_reclaim_confirmed"):
            allowed.append("PREMARKET_HIGH_RECLAIM")
        if event.get("scheduled_event"):
            allowed.append("EVENT_PREPOSITION_STARTER")

    if 0 <= minutes <= 5:
        if gap_pct >= 5 or tape.get("opening_drive_score"):
            allowed.append("OPENING_BURST_HYPER_LONG")
        if gap_pct >= 3 and (tape.get("price_above_open") or tape.get("opening_drive_score")):
            allowed.append("GAP_AND_GO_CONFIRMATION")

    if 5 < minutes <= 90:
        if tape.get("vwap_washout_reclaim_confirmed") or tape.get("vwap_reclaim_confirmed"):
            allowed.append("VWAP_WASHOUT_RECLAIM")
        if tape.get("orb_1min_breakout"):
            allowed.append("ORB_BREAK_1MIN")
        if tape.get("orb_5min_breakout") or tape.get("opening_range_break"):
            allowed.append("ORB_BREAK_5MIN")
        allowed.append("SECOND_LEG_CONTINUATION")

    if event_minutes is not None and 0 <= _f(event_minutes, 999.0) <= 30:
        allowed.append("EVENT_TIMED_HEADLINE_REACTION")
        if event.get("news_release"):
            allowed.append("NEWS_RELEASE_SCALP")

    if halt_reopen:
        allowed.append("HALT_REOPEN_REACTION")

    if minutes >= 90:
        proof_scope = "CONNECTIVITY_ONLY"
        market_open_ready = False
        warnings.append("post_1100_stream_connectivity_only")
        allowed = [mode for mode in allowed if mode in {"EVENT_TIMED_HEADLINE_REACTION", "NEWS_RELEASE_SCALP", "HALT_REOPEN_REACTION"}]

    if blockers:
        allowed = []

    if not allowed:
        allowed = ["NO_TRADE_WAIT"]

    return StrategyRoute(
        ticker=ticker,
        allowed_modes=allowed,
        primary_mode=allowed[0],
        proof_scope=proof_scope,
        exit_manager_present=has_exit_manager,
        market_open_ready=market_open_ready,
        blockers=blockers,
        warnings=warnings,
    )


def runbook_strategy_modes() -> list[str]:
    return list(RUNBOOK_MODES)
