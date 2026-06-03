import yaml

from src.workflows.deep_mini_bridge import repo_root


def _workflow():
    return yaml.safe_load((repo_root() / "config" / "workflow.yaml").read_text())["workflow"]


def test_config_restores_deep_mini_as_primary_live_selector():
    workflow = _workflow()
    research_llm = workflow["research_llm"]
    deep = workflow["deep_research"]
    grok = workflow["grok_research"]

    assert research_llm["primary_provider"] == "openai"
    assert research_llm["primary_mode"] == "deep_mini"
    assert research_llm["primary_role"] == "live_stock_picker"
    assert research_llm["grok_role"] == "social_heat_discovery_and_challenger"
    assert research_llm["openai_deep_research_role"] == "primary_live_selector"
    assert research_llm["ticket_authorizer"] == "governed_deep_research"
    assert deep["mode"] == "deep_mini"
    assert deep["require_for_live_research"] is True
    assert deep["require_grok_for_live_research"] is False
    assert grok["role"] == "x_social_heat_discovery_and_challenger"
    assert grok["can_authorize_live_ticket"] is False
    assert grok["can_override_deep_mini"] is False


def test_trade_authorization_config_blocks_grok_authorizers():
    trade_auth = _workflow()["trade_authorization"]

    assert "openai_deep_mini" in trade_auth["allowed_authorizers"]
    assert "governed_deep_research" in trade_auth["allowed_authorizers"]
    assert "grok_d_research" in trade_auth["disallowed_authorizers"]
    assert "social_only" in trade_auth["disallowed_authorizers"]
    assert trade_auth["one_ticker_only"] is True
    assert trade_auth["backups_research_only"] is True
