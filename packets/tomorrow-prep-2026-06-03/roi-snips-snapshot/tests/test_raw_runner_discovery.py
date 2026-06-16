from src.research.raw_discovery import build_raw_runner_candidates, summarize_raw_discovery
from tests.runbook_helpers import event


def test_raw_runner_preserves_broad_prefilter_candidates() -> None:
    events = [
        event("INFQ", source_name="sec_edgar", official=True),
        event("INFQ", source_name="benzinga", official=False, structured=True, url="https://benzinga.com/infq"),
        event("QTUM", source_name="stocktwits", official=False, social=True, url="https://stocktwits.com/qtum"),
    ]

    rows = build_raw_runner_candidates(events, preserve_top_n=150)
    summary = summarize_raw_discovery(rows)

    assert rows[0]["ticker"] == "INFQ"
    assert rows[0]["raw_touch_count"] == 2
    assert "government_contract_policy_names" in rows[0]["raw_buckets"]
    assert "structured_catalyst" in rows[0]["pre_filter_flags"]
    assert summary["target_raw_candidates_min"] == 100
    assert summary["target_raw_candidates_max"] == 250
    assert summary["acceptable_raw_candidates_min"] == 50
    assert summary["degraded_raw_candidates_min"] == 25
    assert summary["severely_degraded_raw_candidates_min"] == 10
