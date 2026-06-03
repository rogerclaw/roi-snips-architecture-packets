from src.workflows.deep_mini_bridge import deep_mini_artifact_status, write_required_deep_mini_artifacts
from tests.runbook_helpers import ranked_row


def test_deep_mini_artifacts_written_and_incomplete_when_required_run_missing(tmp_path) -> None:
    status = write_required_deep_mini_artifacts(
        tmp_path,
        trading_date="2026-05-29",
        broad_candidates=[{"ticker": "ABCD"}],
        shortlist=[ranked_row("ABCD")],
        context={},
        deep_mini_run=None,
        final_packet={"research_leader": "ABCD", "best_pick": None},
        incomplete_reason="deep_mini_required_for_live_research_not_completed",
    )

    assert status["completed"] is False
    assert status["missing"] == []
    assert status["shortlist_status"] == "failed"
    assert (tmp_path / "deep_mini" / "final_packet.json").exists()
    assert deep_mini_artifact_status(tmp_path)["final_status"] == "NO_TRADE_RESEARCH_INCOMPLETE"
