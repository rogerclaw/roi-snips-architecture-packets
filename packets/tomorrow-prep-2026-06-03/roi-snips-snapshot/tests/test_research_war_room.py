from src.workflows.research_war_room import run_research_war_room
from tests.runbook_helpers import event


def test_research_war_room_degrades_thin_stale_infq_and_mega_cap_pool() -> None:
    result = run_research_war_room(
        [event("INFQ", source_name="sec_edgar")],
        [
            {
                "ticker": "INFQ",
                "catalyst": "old winner",
                "evidence_score": 8,
                "momentum_score": 8,
                "asymmetry_score": 8,
                "freshness_score": 3,
                "market_cap_bucket": "micro",
                "prior_winner": True,
                "has_fresh_catalyst": False,
                "has_live_tape_confirmation": False,
                "lane_tags": ["government_contract"],
            },
            {
                "ticker": "NVDA",
                "catalyst": "generic AI note",
                "evidence_score": 6,
                "momentum_score": 7,
                "asymmetry_score": 3,
                "freshness_score": 8,
                "market_cap_bucket": "mega",
                "lane_tags": ["ai_mega_cap"],
            },
        ],
        prior_winners={"INFQ": {"picked_at": "2026-05-27T12:00:00+00:00"}},
        session={"window": "premarket"},
    )

    assert result.status == "NO_TRADE_RESEARCH_INCOMPLETE"
    assert result.source_breadth_status == "NO_TRADE_RESEARCH_INCOMPLETE"
    assert result.backup_pool_status == "DEGRADED"
    assert "source_breadth_degraded" in result.blockers


def test_research_war_room_reports_source_breadth_and_raw_candidate_status() -> None:
    events = [
        event("ABCD", source_name="sec_edgar", official=True),
        event("EFGH", source_name="benzinga", official=False, structured=True),
        event("IJKL", source_name="grok_x", official=False, social=True),
        event("MNOP", source_name="fda_scout", official=True),
    ]
    candidate = {
        "ticker": "ABCD",
        "catalyst": "fresh FDA clearance",
        "evidence_score": 9,
        "momentum_score": 9,
        "asymmetry_score": 9,
        "freshness_score": 9,
        "market_cap_bucket": "micro",
        "official_source_count": 1,
        "lane_tags": ["fresh_fda"],
        "has_fresh_catalyst": True,
        "has_live_tape_confirmation": True,
    }
    backup = {**candidate, "ticker": "EFGH"}

    result = run_research_war_room(events, [candidate, backup])

    assert result.raw_candidate_count == 4
    assert result.source_breadth_status == "NO_TRADE_RESEARCH_INCOMPLETE"
    assert result.best_pick == "ABCD"
    assert result.tournament["same_style_backup_pool_ok"] is True
