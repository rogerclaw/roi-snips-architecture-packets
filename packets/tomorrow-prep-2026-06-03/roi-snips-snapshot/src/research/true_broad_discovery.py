from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .raw_discovery import build_raw_runner_candidates, summarize_raw_discovery
from .source_breadth_gate import evaluate_source_breadth


@dataclass
class BroadDiscoveryResult:
    status: str
    raw_candidates: list[dict[str, Any]]
    raw_candidate_count: int
    raw_candidate_sources: list[str]
    raw_candidate_buckets: list[str]
    source_breadth: dict[str, Any]
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_true_broad_discovery(events: list[dict[str, Any]], *, preserve_top_n: int = 250) -> BroadDiscoveryResult:
    raw_candidates = build_raw_runner_candidates(events, preserve_top_n=preserve_top_n)
    summary = summarize_raw_discovery(raw_candidates)
    breadth = evaluate_source_breadth(events, raw_candidate_count=summary["raw_candidate_count"])
    limitations = list(breadth.blockers)
    status = "PASS" if breadth.status in {"TARGET", "OPTIMIZED"} else "DEGRADED"
    if breadth.status == "NO_TRADE_RESEARCH_INCOMPLETE":
        status = "NO_TRADE_RESEARCH_INCOMPLETE"
    if not raw_candidates:
        status = "FAILED"
    return BroadDiscoveryResult(
        status=status,
        raw_candidates=raw_candidates,
        raw_candidate_count=summary["raw_candidate_count"],
        raw_candidate_sources=summary["raw_candidate_sources"],
        raw_candidate_buckets=summary["raw_candidate_buckets"],
        source_breadth=breadth.to_dict(),
        limitations=limitations,
    )
