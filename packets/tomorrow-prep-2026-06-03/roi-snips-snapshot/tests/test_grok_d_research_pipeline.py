from src.research.grok_d_research import run_grok_d_research_tournament, run_grok_red_team


def x_heat(ticker="ABCD"):
    return {
        "status": "completed",
        "candidates": [
            {
                "ticker": ticker,
                "attention_velocity_score": 9,
                "key_threads": ["https://x.com/source/status/1"],
                "narrative": "premarket catalyst attention",
            }
        ],
    }


def web_verification(ticker="ABCD", verified=True):
    return {
        "status": "completed",
        "verified_candidates": [
            {
                "ticker": ticker,
                "verified_catalyst": verified,
                "official_sources": ["https://ir.example.com/news"],
                "structured_sources": ["https://benzinga.com/news"],
                "social_sources": [],
                "direct_beneficiary_score": 8,
                "stale_news_risk": 1,
                "dilution_or_offering_risk": 1,
                "already_priced_in_risk": 1,
                "verification_summary": "ABCD announced a current direct catalyst.",
            }
        ],
    }


def test_grok_d_research_can_output_no_trade_when_x_missing():
    result = run_grok_d_research_tournament(seed_packet={}, x_heat_radar={"status": "failed"}, web_verification=web_verification())

    assert result["decision"] == "NO_TRADE"
    assert result["no_trade_reason"] == "x_search_failed_or_unavailable"


def test_grok_d_research_outputs_one_deep_mini_review_candidate():
    result = run_grok_d_research_tournament(seed_packet={}, x_heat_radar=x_heat(), web_verification=web_verification())

    assert result["decision"] == "RECOMMEND_FOR_DEEP_MINI_REVIEW"
    assert result["authorized_candidate"]["ticker"] == "ABCD"
    assert result["research_only_backups"] == []
    red_team = run_grok_red_team(result)
    assert red_team["verdict"] in {"PASS", "PASS_ONLY_WITH_TAPE"}
    assert red_team["should_block_ticket"] is False


def test_x_hype_alone_cannot_authorize_trade():
    result = run_grok_d_research_tournament(seed_packet={}, x_heat_radar=x_heat(), web_verification=web_verification(verified=False))

    assert result["decision"] == "NO_TRADE"
    assert result["no_trade_reason"] == "x_hype_without_hard_verification"
