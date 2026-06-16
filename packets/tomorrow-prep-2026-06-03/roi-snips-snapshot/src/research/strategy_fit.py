from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


MEGA_CAPS = {"AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "AMD", "NFLX", "PLTR", "QQQ", "SMCI", "SPY"}


@dataclass
class StrategyFitResult:
    ticker: str
    status: str
    buyable_now: bool
    strategy_tags: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_strategy_fit(candidate: dict[str, Any], session: dict[str, Any] | None = None) -> StrategyFitResult:
    session = session or {}
    ticker = str(candidate.get("ticker") or "").upper()
    blockers: list[str] = []
    tags: list[str] = []
    market_cap_bucket = str(candidate.get("market_cap_bucket") or candidate.get("market_cap") or "").lower()
    asymmetry = float(candidate.get("asymmetry_score") or candidate.get("asymmetry") or 0.0)
    freshness = float(candidate.get("freshness_score") or candidate.get("freshness") or 0.0)
    momentum = float(candidate.get("momentum_score") or candidate.get("momentum") or 0.0)

    if ticker in MEGA_CAPS and market_cap_bucket in {"", "mega", "large", "large_cap"} and asymmetry < 8.5:
        blockers.append("mega_cap_filler_not_a_tier")
    if freshness < 6.0:
        blockers.append("stale_or_unproven_catalyst")
    if momentum >= 7.5:
        tags.append("momentum_candidate")
    if asymmetry >= 7.5:
        tags.append("asymmetric_candidate")

    window = str(session.get("window") or session.get("market_session") or "unknown").lower()
    buyability = str(candidate.get("buyability") or "").lower()
    if window == "premarket" and buyability in {"buy_now", "market_open_only"}:
        blockers.append("premarket_buy_now_not_allowed")

    status = "A_TIER" if not blockers and {"momentum_candidate", "asymmetric_candidate"}.issubset(tags) else "DEGRADED"
    return StrategyFitResult(ticker=ticker, status=status, buyable_now=not blockers, strategy_tags=tags, blockers=blockers)


def same_style_backup_status(primary: dict[str, Any] | None, backups: list[dict[str, Any]]) -> dict[str, Any]:
    primary_styles = set((primary or {}).get("strategy_tags") or (primary or {}).get("lane_tags") or [])
    viable = []
    for backup in backups:
        backup_styles = set(backup.get("strategy_tags") or backup.get("lane_tags") or [])
        if primary_styles and primary_styles.intersection(backup_styles):
            fit = evaluate_strategy_fit(backup)
            if fit.status == "A_TIER":
                viable.append(backup.get("ticker"))
    status = "PASS" if viable else "DEGRADED"
    return {"status": status, "same_style_backup_pool_ok": bool(viable), "viable_backups": viable}
