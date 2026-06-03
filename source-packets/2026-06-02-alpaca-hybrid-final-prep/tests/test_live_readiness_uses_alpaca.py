from pathlib import Path

import pytest

from src.common.config import load_env_file, load_live_config
from src.workflows.live_readiness import run_live_readiness


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clear_config_caches():
    load_env_file.cache_clear()
    load_live_config.cache_clear()
    yield
    load_env_file.cache_clear()
    load_live_config.cache_clear()


def test_live_readiness_uses_alpaca_and_not_webull_when_credentials_missing(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://api.alpaca.markets")
    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("ALPACA_MARKET_DATA_FEED", "sip")

    result = run_live_readiness(probe_symbol="SPY")
    encoded = str(result).lower()

    assert result["broker_provider"] == "alpaca"
    assert result["market_data_provider"] == "alpaca"
    assert result["broker_runtime"]["provider"] == "alpaca"
    assert result["broker_runtime"]["base_url"] == "https://api.alpaca.markets"
    assert "missing_alpaca_trade_credentials" in result["execution_blockers"]
    assert "webull" not in encoded


def test_final_arming_dry_run_with_live_config_has_no_webull_blocker(monkeypatch, tmp_path):
    from src.workflows import final_live_arming_gate

    cfg = load_live_config()
    monkeypatch.setenv("ROI_SNIPS_TRADE_DATE", "2026-06-03")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setattr(final_live_arming_gate, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(final_live_arming_gate, "load_live_config", lambda: cfg)
    monkeypatch.setattr(
        final_live_arming_gate,
        "check_opening_bell_readiness",
        lambda ignore_arm_guards=True, inspect_broker_state=False: {
            "status": "RED",
            "opening_bell_blockers": ["broker_state_inspection_skipped"],
            "readiness": {
                "broker_provider": "alpaca",
                "broker_runtime": {
                    "provider": "alpaca",
                    "base_url": "https://api.alpaca.markets",
                    "environment": "live",
                },
            },
            "ignored_arm_guard_blockers": [],
            "primary_candidate": None,
            "candidate_specific_readiness": None,
        },
    )

    result = final_live_arming_gate.run_final_live_arming_gate(execute=False)
    encoded = str(result).lower()

    assert result["verdict"] == "NO_GO"
    assert result["armed_live"] is False
    assert result["orders_previewed_now"] is False
    assert result["orders_submitted_now"] is False
    assert "no_valid_trade_authorization_ticket" in result["blockers"]
    assert "webull" not in encoded


def test_explicit_webull_provider_is_isolated_to_legacy_unit_use():
    from src.common.provider_factory import build_trade_adapter, configured_broker_provider

    cfg = {"broker": {"provider": "webull"}}

    assert configured_broker_provider(cfg) == "webull"
    assert build_trade_adapter(cfg).__class__.__name__ == "WebullTradeAdapter"
    assert load_live_config()["broker"]["provider"] == "alpaca"
