from src.research.candidate_packets import build_candidate_research_packets
from src.research.models import MarketOverlay


def test_candidate_packet_contains_chatgpt_pro_style_research_sections():
    ranked = [
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "company_name": "Infleqtion",
                "claim_summary": "INFQ receives CHIPS Department of Commerce funding LOI for quantum computing",
                "catalyst_type_primary": "government_contract",
                "first_seen_at": "2026-05-21T12:20:00+00:00",
                "latest_update_at": "2026-05-21T12:31:00+00:00",
                "events": [
                    {
                        "source_name": "benzinga_newswire",
                        "source_tier": 1,
                        "source_url": "https://example.com/infq",
                        "published_at": "2026-05-21T12:20:00+00:00",
                        "discovered_at": "2026-05-21T12:21:00+00:00",
                        "catalyst_type": "government_contract",
                        "headline": "INFQ receives CHIPS funding LOI",
                        "official_flag": False,
                        "structured_flag": True,
                        "social_flag": False,
                        "credibility_score_initial": 7.8,
                        "notes": ["source=benzinga"],
                    }
                ],
            },
            "research_scorecard": {
                "validation_status": "primary_and_structured_confirmed",
                "official_confirmation_count": 1,
                "structured_confirmation_count": 1,
                "social_confirmation_count": 2,
                "catalyst_strength_score": 8.0,
                "freshness_score": 9.4,
                "attention_acceleration_score": 7.2,
                "crowding_score": 4.8,
                "asymmetry_score": 8.3,
                "story_stage": "developing",
                "notes": ["hard_catalyst_bonus=1.2"],
            },
            "research_priority_score": 8.2,
            "hyper_trade_score": 7.8,
            "lane_tags": ["VERIFIED_CATALYST_RUNNER"],
            "story_stage": "developing",
            "execution_gate": {"passed": True, "execution_readiness_score": 82, "blockers": [], "warnings": []},
        }
    ]
    overlays = {
        "INFQ": MarketOverlay(
            ticker="INFQ",
            observed_at="2026-05-21T12:31:00+00:00",
            prior_close=11.18,
            last_premarket_price=13.7,
            gap_pct=22.54,
            premarket_volume=6_670_000,
            premarket_dollar_volume=91_379_000,
            average_20d_dollar_volume=98_000_000,
            estimated_spread_pct=0.28,
            halt_status="NONE",
            market_cap=None,
            price_band="5_to_20",
            tradeability_gate_pass=True,
            tradeability_notes=[],
            execution_readiness_score=82,
            execution_blockers=[],
            execution_warnings=[],
        )
    }

    packet = build_candidate_research_packets(ranked, overlays, top_n=1)[0]

    assert packet["ticker"] == "INFQ"
    assert packet["validation_status"] == "primary_and_structured_confirmed"
    assert packet["source_confidence"] == "high"
    assert packet["evidence_table"][0]["source_name"] == "benzinga_newswire"
    assert packet["market_snapshot"]["gap_pct"] == 22.54
    assert packet["why_asymmetric"]
    assert packet["why_it_may_be_wrong"]
    assert packet["invalidation_checklist"]
    assert packet["deterministic_trade_gate_status"]["passed"] is True


def test_candidate_packet_dedupes_repeated_evidence_rows():
    ranked = [
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "claim_summary": "INFQ receives CHIPS funding LOI",
                "catalyst_type_primary": "government_contract",
                "events": [
                    {"source_name": "benzinga", "source_url": "https://example.com/infq", "headline": "INFQ receives CHIPS funding LOI", "structured_flag": True},
                    {"source_name": "benzinga", "source_url": "https://example.com/infq", "headline": "INFQ receives CHIPS funding LOI", "structured_flag": True},
                ],
            },
            "research_scorecard": {"validation_status": "structured_confirmed", "structured_confirmation_count": 1},
            "execution_gate": {"passed": False, "blockers": ["market_overlay_missing"], "warnings": []},
        }
    ]

    packet = build_candidate_research_packets(ranked, {}, top_n=1)[0]

    assert packet["ticker"] == "INFQ"
    assert len(packet["evidence_table"]) == 1
