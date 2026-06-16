from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class StaleWinnerResult:
    ticker: str
    executable: bool
    stale_prior_winner: bool
    prior_session_count_checked: int = 0
    recent_roles: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hours_old(iso_value: str | None, now: str | None) -> float | None:
    if not iso_value:
        return None
    try:
        then = datetime.fromisoformat(iso_value.replace("Z", "+00:00")).astimezone(timezone.utc)
        current = datetime.fromisoformat((now or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")).astimezone(timezone.utc)
        return max(0.0, (current - then).total_seconds() / 3600.0)
    except ValueError:
        return None


def evaluate_stale_winner(
    ticker: str,
    prior_winners: dict[str, dict[str, Any]] | list[dict[str, Any]],
    *,
    has_fresh_catalyst: bool,
    has_live_tape_confirmation: bool,
    now: str | None = None,
    stale_after_hours: float = 18.0,
) -> StaleWinnerResult:
    symbol = ticker.upper()
    recent_roles: list[str] = []
    recent_sessions: list[dict[str, Any]] = []
    prior: dict[str, Any] = {}
    if isinstance(prior_winners, list):
        recent_sessions = prior_winners[-10:]
        for session in recent_sessions:
            leader = str(session.get("research_leader") or "").upper()
            primary = str(session.get("executable_primary") or "").upper()
            winner = str(session.get("ticker") or session.get("winner") or "").upper()
            if leader == symbol:
                recent_roles.append("research_leader")
            if primary == symbol:
                recent_roles.append("executable_primary")
            if winner == symbol:
                recent_roles.append("winner")
            if symbol in {leader, primary, winner}:
                prior = session
    else:
        prior = prior_winners.get(symbol) or prior_winners.get(ticker) or {}
        if prior:
            if prior.get("research_leader") == symbol or prior.get("role") == "research_leader":
                recent_roles.append("research_leader")
            if prior.get("executable_primary") == symbol or prior.get("role") == "executable_primary":
                recent_roles.append("executable_primary")
            if not recent_roles:
                recent_roles.append("winner")
    age = _hours_old(prior.get("picked_at") or prior.get("last_won_at") or prior.get("trading_date"), now)
    stale_prior = bool(prior) and (bool(recent_roles) or age is None or age >= stale_after_hours)
    blockers: list[str] = []
    if stale_prior and not has_fresh_catalyst:
        blockers.append("prior_winner_without_fresh_catalyst")
    if stale_prior and not has_live_tape_confirmation:
        blockers.append("prior_winner_without_live_tape_confirmation")
    return StaleWinnerResult(
        ticker=symbol,
        executable=not blockers,
        stale_prior_winner=stale_prior,
        prior_session_count_checked=len(recent_sessions) if isinstance(prior_winners, list) else (1 if prior else 0),
        recent_roles=sorted(set(recent_roles)),
        blockers=blockers,
    )
