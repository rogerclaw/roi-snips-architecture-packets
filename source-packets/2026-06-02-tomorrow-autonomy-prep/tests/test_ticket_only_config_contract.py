from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_live_engine_declares_ticket_only_execution_contract() -> None:
    payload = yaml.safe_load((ROOT / "config" / "workflow.yaml").read_text())
    live_engine = payload["workflow"]["live_engine"]

    assert live_engine["require_trade_authorization_ticket"] is True
    assert live_engine["authorized_ticket_only_execution"] is True
    assert live_engine["allow_watchlist_backup_execution"] is False


def test_live_research_mode_declares_ticket_only_execution_contract() -> None:
    payload = yaml.safe_load((ROOT / "configs" / "live.yaml").read_text())
    research_mode = payload["research_mode"]

    assert research_mode["require_trade_authorization_ticket"] is True
    assert research_mode["authorized_ticket_only_execution"] is True
    assert research_mode["allow_watchlist_backup_execution"] is False
    assert research_mode["deep_mini_required_for_live_research"] is True
    assert research_mode["grok_required_for_live_research"] is False
    assert research_mode["deterministic_fallback_executable_allowed"] is False
