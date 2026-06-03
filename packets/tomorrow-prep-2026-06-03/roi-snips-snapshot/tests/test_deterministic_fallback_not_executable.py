from src.workflows.deep_mini_bridge import DEEP_MINI_REQUIRED_BLOCKER, build_deep_mini_required_no_trade_packet
from tests.runbook_helpers import ranked_row


def test_deterministic_candidates_remain_non_executable_when_deep_mini_required() -> None:
    packet = build_deep_mini_required_no_trade_packet([ranked_row("ABCD")]).to_dict()

    assert packet["research_leader"] == "ABCD"
    assert packet["best_pick"] is None
    assert packet["execution_eligible"] == []
    assert "deterministic_fallback_executable_allowed_false" in packet["caveats"]
    assert DEEP_MINI_REQUIRED_BLOCKER in packet["key_invalidation_risks"]
