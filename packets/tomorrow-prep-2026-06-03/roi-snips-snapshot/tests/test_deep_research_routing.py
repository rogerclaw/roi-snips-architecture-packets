from src.workflows.deep_mini_bridge import build_deep_mini_brief, run_governed_deep_mini
from src.workflows.deep_mini_bridge import repo_root
from tests.runbook_helpers import ranked_row


def test_deep_research_brief_is_bounded_shortlist_not_order_request() -> None:
    brief = build_deep_mini_brief([ranked_row("INFQ")], {"generated_at_utc": "2026-05-27T12:00:00+00:00"})

    assert "bounded deep-mini shortlist synthesis" in brief
    assert "Treat this as research and selection support, not an order request" in brief
    assert "Do not widen the universe beyond the provided shortlist" in brief
    for section in [
        "Objective:",
        "Primary question:",
        "Decision to be made:",
        "Sub-questions to answer:",
        "Known context:",
        "Assumptions to verify:",
        "Scope boundaries:",
        "Out of scope:",
        "Source priorities:",
        "Search plan:",
        "Required deliverable:",
        "Evidence requirements:",
        "Decision criteria:",
        "Stopping condition:",
        "Budget discipline note:",
    ]:
        assert section in brief


def test_governed_deep_research_requires_runner(tmp_path) -> None:
    result = run_governed_deep_mini([ranked_row("INFQ")], {}, tmp_path, deep_cfg={"runner_path": str(tmp_path / "missing-runner")})

    assert result.status == "runner_missing"
    assert result.success is False
    assert "deep_research_runner_missing" in (result.error or "")


def test_live_trade_ready_wrapper_uses_deep_mini_primary_research() -> None:
    script = repo_root() / "scripts" / "run_live_trade_ready_premarket.sh"
    body = script.read_text()

    assert 'ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"' in body
    assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"' in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"' in body
    assert "check_grok_research_readiness.sh" in body
    assert "-m src.workflows.grok_research_pipeline" in body
    assert "-m src.workflows.research_pipeline" in body
    assert "-m src.workflows.research_pipeline --skip-deep-mini" not in body
