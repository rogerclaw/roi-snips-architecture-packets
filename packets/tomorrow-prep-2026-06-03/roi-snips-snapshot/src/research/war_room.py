from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_MEGA_CAPS = {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"}
MIN_TOURNAMENT_SCORE = 45.0


@dataclass
class TournamentCandidate:
    ticker: str
    catalyst: str
    evidence_score: float
    momentum_score: float
    asymmetry_score: float
    freshness_score: float
    market_cap_bucket: str = "unknown"
    prior_winner: bool = False
    official_source_count: int = 0
    social_velocity_score: float = 0.0
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _score(candidate: TournamentCandidate) -> float:
    score = (
        candidate.evidence_score * 2.0
        + candidate.momentum_score * 2.2
        + candidate.asymmetry_score * 2.0
        + candidate.freshness_score * 1.8
        + candidate.social_velocity_score * 0.8
        + min(candidate.official_source_count, 3) * 1.5
    )
    if candidate.prior_winner:
        score -= 18.0
    if candidate.market_cap_bucket == "mega" and candidate.ticker.upper() in DEFAULT_MEGA_CAPS:
        exceptional = candidate.evidence_score >= 8.5 and candidate.momentum_score >= 8.0 and candidate.asymmetry_score >= 7.5
        if not exceptional:
            score -= 14.0
    if candidate.freshness_score < 5.0:
        score -= 10.0
    return round(score, 3)


def _rejection_reasons(candidate: TournamentCandidate, score: float) -> list[str]:
    reasons: list[str] = []
    if candidate.prior_winner:
        reasons.append("stale_prior_winner")
    if candidate.freshness_score < 5.0:
        reasons.append("stale_or_unproven_freshness")
    if candidate.market_cap_bucket == "mega" and candidate.ticker.upper() in DEFAULT_MEGA_CAPS and candidate.asymmetry_score < 7.5:
        reasons.append("boring_mega_cap_fallback")
    if candidate.official_source_count < 1 and candidate.evidence_score < 8.0:
        reasons.append("insufficient_primary_evidence")
    if score < MIN_TOURNAMENT_SCORE:
        reasons.append("below_hyper_trade_threshold")
    return reasons


def run_candidate_tournament(raw_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [TournamentCandidate(**row) for row in raw_candidates]
    scored = [
        {
            "candidate": candidate.to_dict(),
            "score": _score(candidate),
            "rejection_reasons": _rejection_reasons(candidate, _score(candidate)),
        }
        for candidate in candidates
    ]
    ranked = sorted(
        scored,
        key=lambda row: row["score"],
        reverse=True,
    )
    eligible = [row for row in ranked if not row["rejection_reasons"]]
    best = eligible[0]["candidate"]["ticker"] if eligible else None
    stale_blocked = all(not row["candidate"].get("prior_winner") or row["candidate"]["ticker"] != best for row in ranked)
    mega_blocked = all(
        not (
            row["candidate"]["ticker"] == best
            and row["candidate"].get("market_cap_bucket") == "mega"
            and row["candidate"]["ticker"] in DEFAULT_MEGA_CAPS
            and row["candidate"].get("asymmetry_score", 0) < 7.5
        )
        for row in ranked
    )
    return {
        "best_pick": best,
        "ranked": ranked,
        "backup_pool": [row["candidate"]["ticker"] for row in eligible[1:4]],
        "stale_winner_blocked": stale_blocked,
        "mega_cap_fallback_blocked": mega_blocked,
        "no_trade": not bool(best),
        "no_trade_reasons": [] if best else sorted({reason for row in ranked for reason in row["rejection_reasons"]}) or ["no_candidates"],
    }


def build_research_war_room(raw_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    tournament = run_candidate_tournament(raw_candidates)
    return {
        "mode": "chatgpt_pro_style_research_tournament",
        "discovery_lanes": [
            "official_filings_and_ir",
            "newswire_and_local_news",
            "premarket_relative_volume",
            "theme_sympathy_and_policy",
            "social_velocity",
        ],
        "required_packet_fields": [
            "catalyst",
            "primary_evidence",
            "freshness",
            "momentum",
            "asymmetry",
            "risk",
            "thesis_break",
            "profit_taking_triggers",
        ],
        "best_pick": tournament["best_pick"],
        "ranked_count": len(tournament["ranked"]),
        "no_trade": tournament["no_trade"],
    }
