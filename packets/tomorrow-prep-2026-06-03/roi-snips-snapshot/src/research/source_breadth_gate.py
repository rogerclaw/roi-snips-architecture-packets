from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .source_lane_status import REQUIRED_SOURCE_LANES, build_source_lane_status


MIN_REQUIRED_RAN_LANES = 4
MIN_REQUIRED_USEFUL_LANES = 3
TARGET_RAW_CANDIDATE_MIN = 100
ACCEPTABLE_RAW_CANDIDATE_MIN = 50
DEGRADED_RAW_CANDIDATE_MIN = 25
SEVERELY_DEGRADED_RAW_CANDIDATE_MIN = 10
TOP_MOVER_LANES = {"Alpaca News", "Benzinga", "FMP movers", "TradingView-style screener"}
BROAD_WEB_LANES = {"Tavily/Brave/Exa", "Firecrawl/Crawl4AI"}
SOCIAL_LANES = {"StockTwits", "Grok/X", "Reddit"}


@dataclass
class SourceBreadthResult:
    status: str
    raw_candidate_count: int
    ran_lane_count: int
    useful_lane_count: int
    missing_required_lanes: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    raw_candidate_band: str = "UNKNOWN"
    critical_lane_combo_ok: bool = False
    lane_status: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_source_breadth(
    events: list[dict[str, Any]],
    *,
    primary_ticker: str | None = None,
    raw_candidate_count: int | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> SourceBreadthResult:
    lane_status = build_source_lane_status(events, primary_ticker=primary_ticker, errors=errors)
    ran = [row for row in lane_status if row.get("ran")]
    useful = [row for row in lane_status if int(row.get("produced_useful_evidence_count") or 0) > 0]
    missing = [row["lane_name"] for row in lane_status if row["lane_name"] in REQUIRED_SOURCE_LANES and not row.get("ran")]
    candidate_count = int(raw_candidate_count if raw_candidate_count is not None else len({t for e in events for t in e.get("ticker_candidates", [])}))
    ran_lanes = {str(row.get("lane_name")) for row in ran}

    if TARGET_RAW_CANDIDATE_MIN <= candidate_count <= 250:
        raw_band = "TARGET_100_250"
    elif candidate_count > 250:
        raw_band = "ABOVE_TARGET_250_PLUS"
    elif candidate_count >= ACCEPTABLE_RAW_CANDIDATE_MIN:
        raw_band = "ACCEPTABLE_50_PLUS"
    elif candidate_count >= DEGRADED_RAW_CANDIDATE_MIN:
        raw_band = "DEGRADED_25_49"
    elif candidate_count >= SEVERELY_DEGRADED_RAW_CANDIDATE_MIN:
        raw_band = "SEVERELY_DEGRADED_10_24"
    else:
        raw_band = "FAILURE_UNDER_10"

    critical_combo_ok = bool(ran_lanes & TOP_MOVER_LANES) and bool(ran_lanes & BROAD_WEB_LANES) and bool(ran_lanes & SOCIAL_LANES)

    blockers: list[str] = []
    if candidate_count < ACCEPTABLE_RAW_CANDIDATE_MIN:
        blockers.append("raw_candidate_count_below_threshold")
    if candidate_count < SEVERELY_DEGRADED_RAW_CANDIDATE_MIN:
        blockers.append("raw_candidate_count_failure_under_10")
    if not critical_combo_ok:
        blockers.append("missing_critical_top_movers_broad_web_social_combo")
    if len(ran) < MIN_REQUIRED_RAN_LANES:
        blockers.append("too_few_source_lanes_ran")
    if len(useful) < MIN_REQUIRED_USEFUL_LANES:
        blockers.append("too_few_useful_source_lanes")

    status = "OPTIMIZED"
    if raw_band in {"TARGET_100_250", "ABOVE_TARGET_250_PLUS"} and not blockers:
        status = "TARGET"
    elif candidate_count >= ACCEPTABLE_RAW_CANDIDATE_MIN and not blockers:
        status = "OPTIMIZED"
    elif blockers:
        status = "DEGRADED"
    if raw_band == "SEVERELY_DEGRADED_10_24":
        status = "SEVERELY_DEGRADED"
    if raw_band == "FAILURE_UNDER_10":
        status = "NO_TRADE_RESEARCH_INCOMPLETE"
    if candidate_count < DEGRADED_RAW_CANDIDATE_MIN and not critical_combo_ok:
        status = "NO_TRADE_RESEARCH_INCOMPLETE"
    if not events:
        status = "NO_TRADE_RESEARCH_INCOMPLETE"
        blockers.append("no_source_events")

    return SourceBreadthResult(
        status=status,
        raw_candidate_count=candidate_count,
        ran_lane_count=len(ran),
        useful_lane_count=len(useful),
        missing_required_lanes=missing,
        blockers=sorted(set(blockers)),
        raw_candidate_band=raw_band,
        critical_lane_combo_ok=critical_combo_ok,
        lane_status=lane_status,
    )
