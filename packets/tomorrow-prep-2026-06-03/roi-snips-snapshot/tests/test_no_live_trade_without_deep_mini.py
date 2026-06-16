from src.workflows import opening_bell_monitor
from src.workflows.deep_mini_bridge import DEEP_MINI_REQUIRED_BLOCKER


def test_opening_bell_readiness_blocks_live_when_deep_mini_missing(monkeypatch) -> None:
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": True}})
    monkeypatch.setattr(
        opening_bell_monitor,
        "_latest_morning_packet",
        lambda root: {
            "best_pick_candidate": {"symbol": "ABCD"},
            "deep_mini_required_for_live_research": True,
            "deep_mini_shortlist_status": "failed",
            "deep_mini_completed_before_deadline": False,
        },
    )
    monkeypatch.setattr(opening_bell_monitor, "build_live_readiness_report", lambda cfg, **kwargs: {"execution_blockers": [], "full_execution_ready": True})
    monkeypatch.setattr(opening_bell_monitor, "_candidate_specific_readiness", lambda packet, cfg: {"ok": True, "candidates": [], "blockers": []})

    result = opening_bell_monitor.check_opening_bell_readiness()

    assert result["status"] == "RED"
    assert DEEP_MINI_REQUIRED_BLOCKER in result["opening_bell_blockers"]
