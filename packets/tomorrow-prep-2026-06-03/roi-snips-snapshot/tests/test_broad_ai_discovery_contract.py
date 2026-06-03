from src.workflows.broad_ai_discovery import build_broad_ai_candidates, build_broad_ai_discovery_prompt


def test_broad_ai_discovery_runs_before_final_pick_and_records_failures() -> None:
    prompt = build_broad_ai_discovery_prompt("2026-05-27", [{"family": "government_policy_contract", "query": "CHIPS Act funding stock"}])
    assert "Do not choose the final stock" in prompt

    candidates, sources = build_broad_ai_candidates(
        [{"ticker": "INFQ", "raw_catalyst": "funding award", "raw_reason": "government_contract_policy_names", "pre_filter_flags": ["official_catalyst"]}],
        trading_date="2026-05-27",
    )
    assert candidates[0]["ticker"] == "INFQ"
    assert candidates[0]["high_risk_high_upside"] is True
    assert candidates[0]["evidence_split"]["official"] is True
    assert sources

    failed, _ = build_broad_ai_candidates([], trading_date="2026-05-27", failure_reason="source_timeout")
    assert failed[0]["discovery_status"] == "failed"
    assert failed[0]["failure_reason"] == "source_timeout"
