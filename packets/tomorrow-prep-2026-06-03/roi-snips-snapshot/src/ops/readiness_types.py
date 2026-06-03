from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


READY = "READY"
PARTIAL = "PARTIAL"
FAIL = "FAIL"
INTERNAL_FAILURE = "INTERNAL_FAILURE"
CONNECTIVITY_ONLY = "CONNECTIVITY_ONLY"

MARKET_OPEN_READINESS = "MARKET_OPEN_READINESS"
CONTINUATION_READINESS = "CONTINUATION_READINESS"
CONNECTIVITY_ONLY_SCOPE = "CONNECTIVITY_ONLY"
INVALID = "INVALID"


@dataclass
class MorningReadinessResult:
    final_status: str
    proof_scope: str
    ready_for_live: bool
    ready_for_paper: bool
    ready_for_no_order: bool
    canary_passed: bool
    research_war_room_passed: bool
    source_breadth_status: str
    backup_pool_status: str
    same_day_packet_ready: bool
    stream_captured: bool
    opening_burst_window_covered: bool
    continuation_window_covered: bool
    orders_submitted: bool
    broker_account_inspected: bool
    broker_orders_inspected: bool
    broker_positions_inspected: bool
    failure_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    human_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
