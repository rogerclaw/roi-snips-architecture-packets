from src.workflows.deep_mini_bridge import repo_root


def test_live_scripts_require_deep_mini_and_do_not_require_grok():
    root = repo_root()
    premarket = (root / "scripts" / "run_live_trade_ready_premarket.sh").read_text()
    final_gate = (root / "scripts" / "run_final_live_arming_gate.sh").read_text()
    opening = (root / "scripts" / "run_live_opening_trade_ready.sh").read_text()

    for body in [premarket, final_gate, opening]:
        assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"' in body
        assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"' in body

    assert 'ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"' in premarket
    assert "-m src.workflows.grok_research_pipeline" in premarket
    assert "-m src.workflows.research_pipeline" in premarket
    assert premarket.index("-m src.workflows.grok_research_pipeline") < premarket.index("-m src.workflows.research_pipeline")


def test_grok_prompts_are_research_only():
    root = repo_root()
    grok_prompt = (root / "docs" / "prompts" / "grok_first" / "04_GROK_CANDIDATE_DISCOVERY_TOURNAMENT.md").read_text()
    ticket_summary = (root / "docs" / "prompts" / "grok_first" / "06_GROK_TICKET_INPUT_SUMMARY.md").read_text()

    assert "cannot authorize a trade" in grok_prompt
    assert "can_authorize_live_trade" in grok_prompt
    assert "cannot create a live-valid Trade Authorization Ticket" in ticket_summary
