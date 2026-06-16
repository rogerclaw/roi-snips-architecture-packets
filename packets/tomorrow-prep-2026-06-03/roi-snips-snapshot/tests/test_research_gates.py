from src.research.gates import apply_execution_gate, evaluate_cluster
from src.research.models import CandidateCluster, MarketOverlay
from src.research.ranking import rank_clusters_for_research


def _cluster() -> CandidateCluster:
    return CandidateCluster(
        cluster_id="cluster_1",
        primary_ticker="NVDA",
        company_name="NVIDIA",
        events=[],
        catalyst_type_primary="earnings_or_guidance",
        catalyst_types_all=["earnings_or_guidance"],
        first_seen_at="2026-04-15T10:00:00+00:00",
        latest_update_at="2026-04-15T10:15:00+00:00",
        official_sources=["https://sec.gov/test"],
        structured_sources=[],
        social_sources=[],
        obscure_sources=[],
        claim_summary="NVIDIA raises guidance",
        official_confirmed=True,
        source_quality_score=8.0,
        freshness_score=8.0,
        crowdedness_preliminary=2.0,
        unresolved_questions=[],
        elimination_flags=[],
        official_confirmation_count=1,
        structured_confirmation_count=0,
        social_confirmation_count=0,
        obscure_confirmation_count=0,
        catalyst_strength_score=8.0,
        attention_acceleration_score=3.0,
        story_stage_score=7.0,
        asymmetry_score=6.0,
        research_priority_score=7.5,
    )


def _overlay() -> MarketOverlay:
    return MarketOverlay(
        ticker="NVDA",
        observed_at="2026-04-15T11:00:00+00:00",
        prior_close=100.0,
        last_premarket_price=104.0,
        gap_pct=4.0,
        premarket_volume=1000000,
        premarket_dollar_volume=104000000.0,
        average_20d_dollar_volume=50000000.0,
        estimated_spread_pct=0.08,
        halt_status="NONE",
        market_cap=1_000_000_000.0,
        price_band="100_plus",
        tradeability_gate_pass=True,
        tradeability_notes=[],
        execution_readiness_score=85.0,
        execution_blockers=[],
        execution_warnings=[],
    )


def test_evaluate_cluster_passes_good_candidate():
    result = evaluate_cluster(_cluster(), _overlay())
    assert result.passed
    assert result.score > 0


def test_evaluate_cluster_fails_social_only_story():
    cluster = _cluster()
    cluster.official_sources = []
    cluster.structured_sources = []
    cluster.social_sources = ["https://reddit.com/x"]
    result = evaluate_cluster(cluster, _overlay())
    assert not result.passed
    assert "missing_official_or_structured_confirmation" in result.reasons


def test_apply_execution_gate_keeps_speculative_spread_as_penalty_not_blocker():
    ranked = rank_clusters_for_research([_cluster()])
    bad_overlay = _overlay()
    bad_overlay.execution_blockers = ["spread_too_wide"]
    bad_overlay.execution_readiness_score = 40.0
    good, bad = apply_execution_gate(ranked, {"NVDA": bad_overlay})
    assert good
    assert not bad
    assert "spread_wide_size_down" in good[0]["gate_result"]["speculative_risk_penalties"]
    assert "execution_readiness_below_threshold" in good[0]["gate_result"]["speculative_risk_penalties"]


def test_evaluate_cluster_blocks_parabolic_extension_risk():
    cluster = _cluster()
    cluster.story_stage_score = 2.5
    cluster.crowdedness_preliminary = 8.8
    overlay = _overlay()
    overlay.gap_pct = 24.0
    result = evaluate_cluster(cluster, overlay)
    assert result.passed
    assert "parabolic_extension_risk" in result.speculative_risk_penalties
