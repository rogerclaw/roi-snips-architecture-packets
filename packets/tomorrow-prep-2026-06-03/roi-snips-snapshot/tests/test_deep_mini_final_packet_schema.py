from src.research.final_packet_schema import validate_final_packet


def test_deep_mini_final_packet_schema_requires_live_research_fields() -> None:
    validation = validate_final_packet(
        {
            "status": "completed",
            "research_leader": "ABCD",
            "executable_primary": "ABCD",
            "ticker": "ABCD",
            "catalyst": "fresh catalyst",
            "evidence": {"official": [], "structured": [], "social": [], "market_data": []},
            "buy_now_allowed": True,
            "current_action": "WAIT_OPENING_BURST",
            "buy_zone": "wait for tape",
            "same_day_target": "12-14",
            "one_to_three_day_target": "15-18",
            "thesis_break": "below 10",
            "profit_taking_triggers": ["vertical spike"],
            "danger_signals": ["offering"],
            "same_style_backups": [{"ticker": "EFGH"}],
            "same_style_backup_pool_ok": True,
            "mega_cap_backups": [{"ticker": "NVDA", "reason": "rejected blue-chip default"}],
            "source_breadth_status": "PASS",
            "raw_candidate_count": 100,
            "why_winner_wins": "best catalyst",
            "why_not_blue_chip": "not a default mega-cap",
            "why_not_stale_prior_winner": "fresh catalyst",
            "top_rejects": [{"ticker": "NVDA", "reason": "blue-chip default"}],
            "required_live_confirmations": ["spread/tape"],
            "deep_mini_required_for_live_research": True,
            "deep_mini_artifact_paths": {"final_packet": "runs/2026-05-29/deep_mini/final_packet.json"},
            "deep_mini_completed_before_deadline": True,
            "deterministic_fallback_executable_allowed": False,
            "red_team_verdict": "PASS_ONLY_WITH_TAPE",
            "live_execution_readiness_gate_status": "RESEARCH_COMPLETE_TAPE_GATES_STILL_REQUIRED",
        }
    )

    assert validation.valid is True
