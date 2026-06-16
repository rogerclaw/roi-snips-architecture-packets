from src.research.source_breadth_gate import evaluate_source_breadth
from tests.runbook_helpers import event


def test_missing_required_source_lanes_degrades_research() -> None:
    result = evaluate_source_breadth([event("INFQ", source_name="sec_edgar")], raw_candidate_count=1)

    assert result.status == "NO_TRADE_RESEARCH_INCOMPLETE"
    assert result.raw_candidate_band == "FAILURE_UNDER_10"
    assert "raw_candidate_count_below_threshold" in result.blockers
    assert "raw_candidate_count_failure_under_10" in result.blockers
    assert "too_few_source_lanes_ran" in result.blockers
    assert "missing_critical_top_movers_broad_web_social_combo" in result.blockers
    assert "Benzinga" in result.missing_required_lanes


def test_source_breadth_reports_target_raw_candidate_proof() -> None:
    events = [
        event("A", source_name="external_movers_scout", official=False, structured=True),
        event("B", source_name="benzinga", official=False, structured=True),
        event("C", source_name="grok_x", official=False, social=True),
        event("D", source_name="brave", official=False, structured=True),
        event("E", source_name="brave", official=False, structured=True),
    ]
    result = evaluate_source_breadth(events, raw_candidate_count=125)

    assert result.status == "TARGET"
    assert result.raw_candidate_count == 125
    assert result.raw_candidate_band == "TARGET_100_250"
    assert result.critical_lane_combo_ok is True
    assert result.ran_lane_count >= 4
    assert result.useful_lane_count >= 3


def test_source_breadth_accepts_fifty_plus_as_optimized() -> None:
    events = [
        event("A", source_name="external_movers_scout", structured=True),
        event("B", source_name="benzinga", structured=True),
        event("C", source_name="stocktwits", social=True),
        event("D", source_name="firecrawl", structured=True),
    ]
    result = evaluate_source_breadth(events, raw_candidate_count=50)

    assert result.status == "OPTIMIZED"
    assert result.raw_candidate_band == "ACCEPTABLE_50_PLUS"
    assert result.critical_lane_combo_ok is True


def test_source_breadth_enforces_runbook_candidate_bands_and_critical_combo() -> None:
    result = evaluate_source_breadth(
        [
            event("A", source_name="benzinga", official=False, structured=True),
            event("B", source_name="sec_edgar", official=True),
            event("C", source_name="fda_scout", official=True),
        ],
        raw_candidate_count=24,
    )

    assert result.status == "NO_TRADE_RESEARCH_INCOMPLETE"
    assert result.raw_candidate_band == "SEVERELY_DEGRADED_10_24"
    assert "missing_critical_top_movers_broad_web_social_combo" in result.blockers
