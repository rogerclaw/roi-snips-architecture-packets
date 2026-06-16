from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..research.stale_winner_memory import evaluate_stale_winner
from ..research.strategy_fit import evaluate_strategy_fit, same_style_backup_status
from ..research.true_broad_discovery import run_true_broad_discovery
from ..research.war_room import TournamentCandidate, run_candidate_tournament


@dataclass
class ResearchWarRoomResult:
    status: str
    best_pick: str | None
    raw_candidate_count: int
    source_breadth_status: str
    backup_pool_status: str
    stale_winner_result: dict[str, Any] | None
    mega_cap_filler_result: dict[str, Any]
    tournament: dict[str, Any]
    broad_discovery: dict[str, Any]
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_research_war_room(
    events: list[dict[str, Any]],
    tournament_candidates: list[dict[str, Any]],
    *,
    prior_winners: dict[str, dict[str, Any]] | None = None,
    session: dict[str, Any] | None = None,
) -> ResearchWarRoomResult:
    broad = run_true_broad_discovery(events)
    allowed_tournament_fields = set(TournamentCandidate.__dataclass_fields__)
    tournament_input = [
        {key: value for key, value in candidate.items() if key in allowed_tournament_fields}
        for candidate in tournament_candidates
    ]
    tournament = run_candidate_tournament(tournament_input)
    best = tournament.get("best_pick")
    blockers: list[str] = []

    best_candidate = next((row for row in tournament_candidates if str(row.get("ticker")).upper() == str(best or "").upper()), None)
    backups = [row for row in tournament_candidates if str(row.get("ticker")).upper() != str(best or "").upper()]
    backup_status = same_style_backup_status(best_candidate, backups)
    if backup_status["status"] != "PASS":
        blockers.append("same_style_backup_pool_degraded")

    stale_result = None
    if best:
        stale_result = evaluate_stale_winner(
            str(best),
            prior_winners or {},
            has_fresh_catalyst=bool((best_candidate or {}).get("has_fresh_catalyst", True)),
            has_live_tape_confirmation=bool((best_candidate or {}).get("has_live_tape_confirmation", False)),
        ).to_dict()
        if stale_result["executable"] is False:
            blockers.extend(stale_result["blockers"])

    mega_result = {"blocked": False, "reason": None}
    if best_candidate:
        fit = evaluate_strategy_fit(best_candidate, session=session)
        if "mega_cap_filler_not_a_tier" in fit.blockers:
            mega_result = {"blocked": True, "reason": "mega_cap_filler_not_a_tier"}
            blockers.append("mega_cap_filler_not_a_tier")

    if broad.status != "PASS":
        blockers.append("source_breadth_degraded")
    if tournament.get("no_trade"):
        blockers.extend(tournament.get("no_trade_reasons") or ["no_trade"])

    status = "PASS" if not blockers else "DEGRADED"
    if broad.status == "NO_TRADE_RESEARCH_INCOMPLETE":
        status = "NO_TRADE_RESEARCH_INCOMPLETE"
    if not best:
        status = "NO_TRADE_RESEARCH_INCOMPLETE"

    return ResearchWarRoomResult(
        status=status,
        best_pick=best,
        raw_candidate_count=broad.raw_candidate_count,
        source_breadth_status=broad.source_breadth["status"],
        backup_pool_status=backup_status["status"],
        stale_winner_result=stale_result,
        mega_cap_filler_result=mega_result,
        tournament={**tournament, **backup_status},
        broad_discovery=broad.to_dict(),
        blockers=sorted(set(blockers)),
    )
