from src.workflows.deep_mini_bridge import repo_root


def test_live_wrapper_defaults_to_deep_mini_primary_with_grok_heat_layer() -> None:
    body = (repo_root() / "scripts" / "run_live_trade_ready_premarket.sh").read_text()

    assert 'ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"' in body
    assert "ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH" in body
    assert "ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH" in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false' in body
    assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true' in body
    assert 'ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS:-1800' in body
    assert "LIVE_READINESS_RC" in body
    assert "premarket_research_continues;final_arming_gate_enforces_go_no_go" in body
    assert "check_grok_research_readiness.sh" in body
    assert "-m src.workflows.grok_research_pipeline" in body
    assert "-m src.workflows.research_pipeline" in body
    assert "GROK_RESEARCH_RC" in body
    assert "DEEP_RESEARCH_RC" in body
    assert "grok_research_only_feeds_deep_mini;final_arming_gate_enforces_deep_mini_ticket" in body
    assert "deep_mini_primary_live_selector;final_arming_gate_enforces_deep_mini_ticket" in body


def test_skip_deep_mini_paths_are_labeled_smoke_not_live() -> None:
    root = repo_root()
    for relative in ["scripts/run_next_open_shadow_validation.py", "scripts/run_mechanical_checks.sh"]:
        body = (root / relative).read_text()
        assert "--skip-deep-mini" in body
        assert "SMOKE_SKIP_DEEP_MINI_NOT_FOR_LIVE_SELECTION" in body
