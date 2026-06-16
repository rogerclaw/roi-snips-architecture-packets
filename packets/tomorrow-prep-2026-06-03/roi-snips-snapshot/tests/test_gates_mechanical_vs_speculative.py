from src.research.gates import evaluate_cluster
from src.research.models import CandidateCluster, MarketOverlay


def _social_cluster() -> CandidateCluster:
    return CandidateCluster(
        cluster_id="cluster_social",
        primary_ticker="ROKT",
        company_name="Rocket Test",
        events=[{"headline": "ROKT low float squeeze chatter"}],
        catalyst_type_primary="social_acceleration",
        catalyst_types_all=["social_acceleration"],
        first_seen_at="2026-05-20T12:00:00+00:00",
        latest_update_at="2026-05-20T12:05:00+00:00",
        official_sources=[],
        structured_sources=[],
        social_sources=["https://x.com/a", "https://x.com/b", "https://x.com/c", "https://x.com/d"],
        obscure_sources=[],
        claim_summary="ROKT low float squeeze chatter",
        official_confirmed=False,
        source_quality_score=5.5,
        freshness_score=8.5,
        crowdedness_preliminary=4.0,
        unresolved_questions=[],
        elimination_flags=[],
        official_confirmation_count=0,
        structured_confirmation_count=0,
        social_confirmation_count=4,
        obscure_confirmation_count=0,
        catalyst_strength_score=6.2,
        attention_acceleration_score=9.2,
        story_stage_score=8.0,
        asymmetry_score=8.0,
        research_priority_score=0.0,
    )


def _overlay(**kwargs) -> MarketOverlay:
    defaults = {
        "ticker": "ROKT",
        "observed_at": "2026-05-20T12:10:00+00:00",
        "prior_close": 4.0,
        "last_premarket_price": 4.65,
        "gap_pct": 16.25,
        "premarket_volume": 900000,
        "premarket_dollar_volume": 4_185_000.0,
        "average_20d_dollar_volume": 6_000_000.0,
        "estimated_spread_pct": 0.95,
        "halt_status": "NONE",
        "market_cap": 90_000_000.0,
        "price_band": "sub_5",
        "tradeability_gate_pass": True,
        "tradeability_notes": [],
        "execution_readiness_score": 74.0,
        "execution_blockers": ["price_below_execution_floor", "avg_dollar_volume_below_execution_floor", "spread_too_wide"],
        "execution_warnings": [],
    }
    defaults.update(kwargs)
    return MarketOverlay(**defaults)


def test_social_tape_rocket_can_pass_research_gate_with_speculative_penalties():
    result = evaluate_cluster(_social_cluster(), _overlay())
    assert result.passed
    assert result.hard_blockers == []
    assert "missing_official_or_structured_confirmation_social_tape_exception" in result.speculative_risk_penalties
    assert "spread_wide_size_down" in result.speculative_risk_penalties


def test_mechanical_missing_spread_still_blocks():
    overlay = _overlay(estimated_spread_pct=None, execution_blockers=["spread_estimate_missing"])
    result = evaluate_cluster(_social_cluster(), overlay)
    assert not result.passed
    assert "spread_estimate_missing" in result.hard_blockers


def test_mechanically_impossible_spread_blocks():
    overlay = _overlay(estimated_spread_pct=2.5, execution_blockers=["spread_too_wide"])
    result = evaluate_cluster(_social_cluster(), overlay)
    assert not result.passed
    assert "spread_mechanically_too_wide" in result.hard_blockers
