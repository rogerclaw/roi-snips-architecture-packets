from src.ops.openclaw_cron_policy import evaluate_openclaw_cron_run


def test_runtime_ok_with_command_unavailable_is_not_ready() -> None:
    result = evaluate_openclaw_cron_run(
        runtime_status="ok",
        assistant_summary="FAILURE command unavailable: shell/exec not exposed",
        expected_artifact_exists=True,
        expected_artifact_updated_after_schedule=True,
    )

    assert result.ready is False
    assert "assistant_summary_command_unavailable" in result.blockers


def test_runtime_ok_with_missing_or_stale_artifact_is_not_ready() -> None:
    result = evaluate_openclaw_cron_run(
        runtime_status="ok",
        assistant_summary="OK",
        expected_artifact_exists=False,
        expected_artifact_updated_after_schedule=False,
    )

    assert result.ready is False
    assert "expected_artifact_missing" in result.blockers
    assert "expected_artifact_stale" in result.blockers


def test_runtime_ok_explicit_ok_and_updated_artifact_is_ready() -> None:
    result = evaluate_openclaw_cron_run(
        runtime_status="ok",
        assistant_summary="OK",
        expected_artifact_exists=True,
        expected_artifact_updated_after_schedule=True,
    )

    assert result.ready is True
    assert result.blockers == []
