from pathlib import Path

import yaml

from src.common.config import load_live_config
from src.common.provider_factory import (
    build_market_data_adapter,
    build_trade_adapter,
    configured_broker_provider,
    configured_market_data_provider,
)


ROOT = Path(__file__).resolve().parents[1]


def test_live_config_uses_alpaca_broker_and_sip_market_data():
    cfg = load_live_config()

    assert cfg["broker"]["provider"] == "alpaca"
    assert cfg["broker"]["environment"] == "live"
    assert cfg["broker"]["base_url"] == "https://api.alpaca.markets"
    assert cfg["broker"]["broker_role"] == "data_and_execution"
    assert cfg["market_data"]["provider"] == "alpaca"
    assert cfg["market_data"]["required_feed_for_full_mode"] == "sip"
    assert configured_broker_provider(cfg) == "alpaca"
    assert configured_market_data_provider(cfg) == "alpaca"
    assert build_trade_adapter(cfg).__class__.__name__ == "AlpacaTradeAdapter"
    assert build_market_data_adapter(cfg).__class__.__name__ == "AlpacaMarketDataAdapter"


def test_live_config_preserves_ticket_only_deep_mini_contract():
    cfg = load_live_config()
    research_mode = cfg["research_mode"]

    assert research_mode["require_trade_authorization_ticket"] is True
    assert research_mode["authorized_ticket_only_execution"] is True
    assert research_mode["allow_watchlist_backup_execution"] is False
    assert research_mode["deep_mini_required_for_live_research"] is True
    assert research_mode["grok_required_for_live_research"] is False
    assert research_mode["grok_only_ticket_executable_allowed"] is False
    assert research_mode["deterministic_fallback_executable_allowed"] is False


def test_live_config_contains_no_webull_runtime_selection():
    live_text = (ROOT / "configs" / "live.yaml").read_text()
    cfg = yaml.safe_load(live_text)

    assert cfg["broker"]["provider"] == "alpaca"
    assert "provider: webull" not in live_text
    assert "api.webull.com" not in live_text


def test_paper_example_uses_alpaca_paper_when_present():
    paper_example = ROOT / "configs" / "paper.example.yaml"
    if not paper_example.exists():
        return

    cfg = yaml.safe_load(paper_example.read_text())
    assert cfg["broker"]["provider"] == "alpaca"
    assert cfg["broker"]["environment"] == "paper"
    assert cfg["broker"]["base_url"] == "https://paper-api.alpaca.markets"
