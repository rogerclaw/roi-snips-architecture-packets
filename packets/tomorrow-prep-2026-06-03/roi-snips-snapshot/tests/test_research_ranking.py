import json
from pathlib import Path

from src.research.models import CandidateCluster
from src.research.ranking import rank_clusters_for_research


def _cluster(ticker: str, *, official=0, structured=1, social=0, obscure=0, catalyst=5.5, freshness=8.5, attention=3.0, crowding=2.0, asymmetry=6.0):
    return CandidateCluster(
        cluster_id=f"cluster_{ticker}",
        primary_ticker=ticker,
        company_name=ticker,
        events=[],
        catalyst_type_primary="product_or_partnership",
        catalyst_types_all=["product_or_partnership"],
        first_seen_at="2026-04-30T13:00:00+00:00",
        latest_update_at="2026-04-30T13:15:00+00:00",
        official_sources=[f"https://example.com/{ticker}/official"] if official else [],
        structured_sources=[f"https://example.com/{ticker}/structured/{i}" for i in range(structured)],
        social_sources=[f"https://example.com/{ticker}/social/{i}" for i in range(social)],
        obscure_sources=[f"https://example.com/{ticker}/obscure/{i}" for i in range(obscure)],
        claim_summary=f"{ticker} catalyst",
        official_confirmed=bool(official),
        source_quality_score=7.2,
        freshness_score=freshness,
        crowdedness_preliminary=crowding,
        unresolved_questions=[],
        elimination_flags=[],
        official_confirmation_count=official,
        structured_confirmation_count=structured,
        social_confirmation_count=social,
        obscure_confirmation_count=obscure,
        catalyst_strength_score=catalyst,
        attention_acceleration_score=attention,
        story_stage_score=8.0,
        asymmetry_score=asymmetry,
        research_priority_score=0.0,
    )


def test_rank_clusters_prefers_obscure_small_cap_style_over_megacap_when_similar():
    ranked = rank_clusters_for_research([
        _cluster("NVDA", official=1, structured=1, obscure=0, catalyst=5.9, freshness=8.7, attention=3.2, crowding=3.0, asymmetry=6.2),
        _cluster("MRAM", official=0, structured=1, obscure=1, catalyst=5.8, freshness=8.6, attention=3.1, crowding=2.0, asymmetry=6.5),
    ])
    assert ranked[0]["ticker"] == "MRAM"
    assert "megacap_penalty_applied" in ranked[1]["research_scorecard"]["notes"]


def test_rank_clusters_penalizes_social_only_hype():
    ranked = rank_clusters_for_research([
        _cluster("ABEO", official=0, structured=0, social=3, obscure=0, catalyst=5.4, freshness=8.8, attention=6.5, crowding=6.8, asymmetry=5.5),
        _cluster("MRAM", official=0, structured=1, social=1, obscure=1, catalyst=5.0, freshness=8.3, attention=3.2, crowding=2.2, asymmetry=6.3),
    ])
    assert ranked[0]["ticker"] == "MRAM"
    social_notes = ranked[1]["research_scorecard"]["notes"]
    assert "social_only_penalty_applied" in social_notes
    assert ranked[1]["research_scorecard"]["validation_status"] == "social_discovery_only"


def test_rank_clusters_prefers_infq_style_government_quantum_setup_over_boring_megacap_filing():
    amd = _cluster("AMD", official=1, structured=0, social=0, obscure=0, catalyst=4.8, freshness=8.8, attention=2.8, crowding=3.5, asymmetry=4.8)
    amd.catalyst_type_primary = "filing_update"
    amd.catalyst_types_all = ["filing_update"]
    amd.claim_summary = "AMD 8-K filing update"

    infq = _cluster("INFQ", official=1, structured=2, social=2, obscure=1, catalyst=6.7, freshness=9.3, attention=7.2, crowding=5.0, asymmetry=8.1)
    infq.catalyst_type_primary = "government_contract"
    infq.catalyst_types_all = ["government_contract"]
    infq.claim_summary = "INFQ quantum company receives proposed CHIPS government funding LOI and presents today"

    ranked = rank_clusters_for_research([amd, infq])

    assert ranked[0]["ticker"] == "INFQ"
    assert ranked[0]["research_scorecard"]["validation_status"] == "primary_and_structured_confirmed"
    assert any(str(note).startswith("hard_catalyst_bonus=") for note in ranked[0]["research_scorecard"]["notes"])
    assert "megacap_penalty_applied" in ranked[1]["research_scorecard"]["notes"]
    assert ranked[1]["mega_cap_fallback_audit"]["demote_unless_exceptional"] is True


def test_infq_manual_winner_fixture_outranks_common_fallback_basket():
    fixture = json.loads(Path("tests/fixtures/manual_winners/INFQ_2026_05_21_case.json").read_text())
    infq = _cluster(
        fixture["ticker"],
        official=1,
        structured=2,
        social=3,
        obscure=1,
        catalyst=7.4,
        freshness=9.5,
        attention=8.2,
        crowding=5.5,
        asymmetry=8.6,
    )
    infq.catalyst_type_primary = fixture["catalyst"]["type"]
    infq.catalyst_types_all = [fixture["catalyst"]["type"]]
    infq.claim_summary = fixture["catalyst"]["summary"]
    infq.events = [
        {
            "headline": fixture["catalyst"]["summary"],
            "raw_text": " ".join(fixture["catalyst"]["terms"]) + " sector basket=" + ",".join(fixture["sector_basket"]),
            "notes": [
                f"gap_pct={fixture['premarket']['gap_pct']}",
                f"premarket_dollar_volume={fixture['premarket']['dollar_volume']}",
                "mentions=18",
            ],
        }
    ]
    clusters = [infq]
    for ticker in fixture["expected_ranking"]["must_outrank"]:
        fallback = _cluster(ticker, official=1, structured=0, social=0, obscure=0, catalyst=4.5, freshness=8.0, attention=2.0, crowding=3.0, asymmetry=4.5)
        fallback.catalyst_type_primary = "filing_update"
        fallback.catalyst_types_all = ["filing_update"]
        fallback.claim_summary = f"{ticker} generic 8-K filing noise"
        clusters.append(fallback)

    ranked = rank_clusters_for_research(clusters)

    assert ranked[0]["ticker"] == "INFQ"
    for row in ranked[1:]:
        if row["ticker"] in fixture["expected_ranking"]["must_outrank"]:
            assert row["mega_cap_fallback_audit"]["demote_unless_exceptional"] is True
