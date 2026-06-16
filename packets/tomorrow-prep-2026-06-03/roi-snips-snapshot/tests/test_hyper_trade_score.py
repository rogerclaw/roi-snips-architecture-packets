from src.research.hyper_trade_score import score_hyper_trade
from src.research.lane_classifier import classify_candidate_lanes
from src.research.models import CandidateCluster, MarketOverlay


def _cluster(ticker="ROKT", *, official=0, structured=0, social=4, attention=9.2, catalyst=6.0, story=8.0, crowding=4.0):
    return CandidateCluster(
        cluster_id=f"cluster_{ticker}",
        primary_ticker=ticker,
        company_name=ticker,
        events=[{"headline": f"{ticker} low float squeeze chatter"}],
        catalyst_type_primary="social_acceleration",
        catalyst_types_all=["social_acceleration"],
        first_seen_at="2026-05-20T12:00:00+00:00",
        latest_update_at="2026-05-20T12:05:00+00:00",
        official_sources=["https://example.com/official"] if official else [],
        structured_sources=["https://example.com/news"] if structured else [],
        social_sources=[f"https://x.com/test/{i}" for i in range(social)],
        obscure_sources=[],
        claim_summary=f"{ticker} low float short squeeze chatter",
        official_confirmed=bool(official),
        source_quality_score=5.5,
        freshness_score=8.8,
        crowdedness_preliminary=crowding,
        unresolved_questions=[],
        elimination_flags=[],
        official_confirmation_count=official,
        structured_confirmation_count=structured,
        social_confirmation_count=social,
        obscure_confirmation_count=0,
        catalyst_strength_score=catalyst,
        attention_acceleration_score=attention,
        story_stage_score=story,
        asymmetry_score=8.0,
        research_priority_score=0.0,
    )


def _overlay(spread_pct=0.6, gap_pct=14.0, readiness=76.0):
    return MarketOverlay(
        ticker="ROKT",
        observed_at="2026-05-20T12:10:00+00:00",
        prior_close=4.0,
        last_premarket_price=4.56,
        gap_pct=gap_pct,
        premarket_volume=800000,
        premarket_dollar_volume=3_600_000.0,
        average_20d_dollar_volume=7_000_000.0,
        estimated_spread_pct=spread_pct,
        halt_status="NONE",
        market_cap=120_000_000.0,
        price_band="sub_5",
        tradeability_gate_pass=True,
        tradeability_notes=[],
        execution_readiness_score=readiness,
        execution_blockers=[],
        execution_warnings=[],
    )


def test_classifies_extreme_social_and_tape_as_social_tape_rocket():
    lanes = classify_candidate_lanes(_cluster(), _overlay())
    assert "SOCIAL_TAPE_ROCKET" in lanes
    assert "MOVER_FIRST_EXPLAIN_LATER" in lanes


def test_hyper_trade_score_penalizes_boring_megacap():
    small = score_hyper_trade(_cluster("ROKT", social=3, attention=8.5), _overlay())
    mega = score_hyper_trade(_cluster("NVDA", official=1, structured=1, social=0, attention=3.0, catalyst=5.0), _overlay(gap_pct=2.0))
    assert small["hyper_trade_score"] > mega["hyper_trade_score"]
    assert mega["components"]["mega_cap_boring_penalty"] > 0
