from src.research.candidate_packets import build_candidate_research_packets
from tests.runbook_helpers import overlay, ranked_row


def test_candidate_packet_contains_enriched_runbook_fields() -> None:
    packet = build_candidate_research_packets([ranked_row("INFQ")], {"INFQ": overlay("INFQ")}, top_n=1)[0]

    for key in [
        "ticker",
        "headline_thesis",
        "first_seen_at_utc",
        "current_buyability_summary",
        "evidence_table",
        "market_snapshot",
        "why_asymmetric",
        "why_it_may_be_wrong",
        "invalidation_checklist",
        "deterministic_trade_gate_status",
    ]:
        assert key in packet
    assert packet["source_confidence"] == "high"
    assert packet["deterministic_trade_gate_status"]["passed"] is True
