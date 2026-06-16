from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class OpenClawCronEvaluation:
    ready: bool
    blockers: list[str]
    runtime_status: str | None
    assistant_summary: str
    artifact_exists: bool
    artifact_updated_after_schedule: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_openclaw_cron_run(
    *,
    runtime_status: str | None,
    assistant_summary: str | None,
    expected_artifact_exists: bool,
    expected_artifact_updated_after_schedule: bool,
) -> OpenClawCronEvaluation:
    summary = assistant_summary or ""
    blockers: list[str] = []
    if runtime_status != "ok":
        blockers.append("cron_runtime_not_ok")
    if "FAILURE command unavailable" in summary:
        blockers.append("assistant_summary_command_unavailable")
    if summary.strip() != "OK":
        blockers.append("assistant_summary_not_explicit_ok")
    if not expected_artifact_exists:
        blockers.append("expected_artifact_missing")
    if not expected_artifact_updated_after_schedule:
        blockers.append("expected_artifact_stale")
    return OpenClawCronEvaluation(
        ready=not blockers,
        blockers=blockers,
        runtime_status=runtime_status,
        assistant_summary=summary,
        artifact_exists=expected_artifact_exists,
        artifact_updated_after_schedule=expected_artifact_updated_after_schedule,
    )
