from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


FAILURE_BUCKETS = [
    "source_lane_failures",
    "ranking_failures",
    "execution_failures",
    "prompt_failures",
]


@dataclass
class PostMissAuditResult:
    status: str
    post_miss_learning: dict[str, Any]
    source_lane_failures: list[str] = field(default_factory=list)
    ranking_failures: list[str] = field(default_factory=list)
    execution_failures: list[str] = field(default_factory=list)
    prompt_failures: list[str] = field(default_factory=list)
    broker_action: str = "NONE"
    orders_submitted: bool = False
    generated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _failure_names(rows: list[dict[str, Any]], key: str, fallback: str) -> list[str]:
    out: list[str] = []
    for row in rows:
        if row.get("ok") is True or row.get("status") in {"OK", "PASS", "READY"}:
            continue
        out.append(str(row.get(key) or row.get("name") or row.get("lane_name") or fallback))
    return sorted(set(out))


def build_post_miss_audit(
    *,
    source_lane_status: list[dict[str, Any]] | None = None,
    ranking_report: dict[str, Any] | None = None,
    execution_report: dict[str, Any] | None = None,
    prompt_report: dict[str, Any] | None = None,
    missed_symbol: str | None = None,
) -> PostMissAuditResult:
    source_lane_status = source_lane_status or []
    ranking_report = ranking_report or {}
    execution_report = execution_report or {}
    prompt_report = prompt_report or {}

    source_failures = [
        str(row.get("lane_name") or row.get("name"))
        for row in source_lane_status
        if not row.get("ran") or row.get("errors") or (row.get("configured") is False and row.get("missing_credentials"))
    ]
    ranking_failures = _failure_names(ranking_report.get("failures") or [], "reason", "ranking_failure")
    if ranking_report.get("best_pick") is None:
        ranking_failures.append("missing_best_pick")
    if ranking_report.get("stale_winner_blocked") is False:
        ranking_failures.append("stale_winner_not_blocked")
    if ranking_report.get("mega_cap_fallback_blocked") is False:
        ranking_failures.append("mega_cap_fallback_not_blocked")

    execution_failures = _failure_names(execution_report.get("failures") or [], "reason", "execution_failure")
    for key in ["stream_missing", "opening_burst_window_not_covered", "no_exit_manager", "broker_action_attempted"]:
        if execution_report.get(key):
            execution_failures.append(key)
    if execution_report.get("broker_action") not in {None, "NONE"}:
        execution_failures.append("broker_action_attempted")

    prompt_failures = _failure_names(prompt_report.get("failures") or [], "field", "prompt_failure")
    for field_name in prompt_report.get("missing_fields") or []:
        prompt_failures.append(f"missing_prompt_field:{field_name}")

    status = "RECORDED" if any([source_failures, ranking_failures, execution_failures, prompt_failures]) else "CLEAN"
    post_miss_learning = {
        "captures_missed_runner_reason": True,
        "records_source_lane_failures": True,
        "records_ranking_failures": True,
        "records_execution_failures": True,
        "records_prompt_failures": True,
        "missed_symbol": missed_symbol,
        "status": status,
        "broker_action": "NONE",
        "orders_submitted": False,
        "failure_counts": {
            "source_lane": len(set(source_failures)),
            "ranking": len(set(ranking_failures)),
            "execution": len(set(execution_failures)),
            "prompt": len(set(prompt_failures)),
        },
    }
    return PostMissAuditResult(
        status=status,
        post_miss_learning=post_miss_learning,
        source_lane_failures=sorted(set(source_failures)),
        ranking_failures=sorted(set(ranking_failures)),
        execution_failures=sorted(set(execution_failures)),
        prompt_failures=sorted(set(prompt_failures)),
    )


def build_slice5_artifacts(
    *,
    continuation_result: dict[str, Any],
    event_result: dict[str, Any],
    post_miss_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "continuation_engine": continuation_result.get("continuation_engine") or continuation_result,
        "event_timed_engine": event_result.get("event_timed_engine") or event_result,
        "post_miss_learning": post_miss_result.get("post_miss_learning") or post_miss_result,
    }
