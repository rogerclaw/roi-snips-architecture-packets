from tests.test_no_red_readiness_arming import test_red_readiness_cannot_arm_even_with_valid_ticket
from src.workflows.final_live_arming_gate import _deep_mini_reached_blockers


def test_final_gate_blocks_red_readiness(monkeypatch):
    test_red_readiness_cannot_arm_even_with_valid_ticket(monkeypatch)


def test_final_gate_blocks_when_deep_mini_was_never_reached(tmp_path):
    assert _deep_mini_reached_blockers(tmp_path, "2099-06-01") == ["premarket_research_never_reached_deep_mini"]


def test_final_gate_accepts_same_day_deep_mini_status(tmp_path):
    status_path = tmp_path / "reports" / "live_monitor" / "live_trade_ready" / "research_latest.status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        '{"trade_date":"2099-06-01","step":"governed_deep_research_pipeline","exit_code":0,'
        '"deep_mini_required":true,"deep_mini_reached":true}'
    )

    assert _deep_mini_reached_blockers(tmp_path, "2099-06-01") == []
