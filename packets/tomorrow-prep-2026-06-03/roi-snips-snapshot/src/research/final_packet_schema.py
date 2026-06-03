from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


REQUIRED_FINAL_PACKET_FIELDS = [
    "status",
    "research_leader",
    "executable_primary",
    "ticker",
    "catalyst",
    "evidence",
    "buy_now_allowed",
    "current_action",
    "buy_zone",
    "same_day_target",
    "one_to_three_day_target",
    "thesis_break",
    "profit_taking_triggers",
    "danger_signals",
    "same_style_backups",
    "same_style_backup_pool_ok",
    "mega_cap_backups",
    "source_breadth_status",
    "raw_candidate_count",
    "why_winner_wins",
    "why_not_blue_chip",
    "why_not_stale_prior_winner",
    "top_rejects",
    "required_live_confirmations",
    "deep_mini_required_for_live_research",
    "deep_mini_artifact_paths",
    "deep_mini_completed_before_deadline",
    "deterministic_fallback_executable_allowed",
    "red_team_verdict",
    "live_execution_readiness_gate_status",
]


@dataclass
class FinalPacketValidation:
    valid: bool
    missing_fields: list[str] = field(default_factory=list)
    packet: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_final_packet(packet: dict[str, Any]) -> FinalPacketValidation:
    missing = [field for field in REQUIRED_FINAL_PACKET_FIELDS if packet.get(field) in (None, "", [])]
    return FinalPacketValidation(valid=not missing, missing_fields=missing, packet=packet)
