from src.workflows.deep_mini_bridge import (
    DEEP_MINI_REQUIRED_BLOCKER,
    build_deep_mini_required_no_trade_packet,
    deep_mini_required_for_live_research,
)
from tests.runbook_helpers import ranked_row


def test_env_makes_deep_mini_required_for_live(monkeypatch) -> None:
    monkeypatch.setenv("ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH", "true")

    assert deep_mini_required_for_live_research({}) is True


def test_live_config_research_mode_makes_deep_mini_required_without_env(monkeypatch) -> None:
    monkeypatch.delenv("ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH", raising=False)
    monkeypatch.delenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", raising=False)

    assert deep_mini_required_for_live_research({}, {"deep_mini_required_for_live_research": True}) is True


def test_missing_deep_mini_builds_no_trade_packet() -> None:
    packet = build_deep_mini_required_no_trade_packet([ranked_row("ABCD")]).to_dict()

    assert packet["best_pick"] is None
    assert packet["execution_eligible"] == []
    assert DEEP_MINI_REQUIRED_BLOCKER in packet["caveats"]
    assert packet["source_mode"] == "deep_mini_required_no_trade"
