import importlib.util
import json
from pathlib import Path

from src.research.archetypes.policy_theme_runner import score_policy_theme_runner_archetype
from src.research.models import CandidateCluster, MarketOverlay
from src.research.source_lane_status import REQUIRED_SOURCE_LANES, build_source_lane_status
from src.workflows import premarket_pipeline


ROOT = Path(__file__).resolve().parents[1]


def _load_script(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _cluster(ticker: str, text: str, *, catalyst: str = "government_contract", official: int = 1, structured: int = 2, social: int = 1) -> CandidateCluster:
    return CandidateCluster(
        cluster_id=f"cluster_{ticker}",
        primary_ticker=ticker,
        company_name=ticker,
        events=[{"headline": text, "raw_text": text, "notes": ["gap_pct=42.9", "premarket_dollar_volume=120000000"]}],
        catalyst_type_primary=catalyst,
        catalyst_types_all=[catalyst],
        first_seen_at="2026-05-22T12:00:00+00:00",
        latest_update_at="2026-05-22T13:00:00+00:00",
        official_sources=["https://example.com/official"] * official,
        structured_sources=["https://example.com/news"] * structured,
        social_sources=["https://x.com/test"] * social,
        obscure_sources=[],
        claim_summary=text,
        official_confirmed=bool(official),
        source_quality_score=8.0,
        freshness_score=9.0,
        crowdedness_preliminary=4.0,
        unresolved_questions=[],
        elimination_flags=[],
        official_confirmation_count=official,
        structured_confirmation_count=structured,
        social_confirmation_count=social,
        catalyst_strength_score=8.0,
        attention_acceleration_score=7.0,
        story_stage_score=8.0,
        asymmetry_score=8.0,
    )


def _overlay(ticker: str, gap: float = 42.9) -> MarketOverlay:
    return MarketOverlay(
        ticker=ticker,
        observed_at="2026-05-22T13:10:00+00:00",
        prior_close=11.29,
        last_premarket_price=16.12,
        gap_pct=gap,
        premarket_volume=8_770_000,
        premarket_dollar_volume=120_000_000,
        average_20d_dollar_volume=5_000_000,
        estimated_spread_pct=0.22,
        halt_status="NONE",
        market_cap=250_000_000,
        price_band="mid",
        tradeability_gate_pass=True,
        tradeability_notes=[],
        execution_readiness_score=88.0,
        execution_blockers=[],
        execution_warnings=[],
    )


def test_policy_theme_runner_is_ticker_neutral_and_demotes_stale_or_indirect_names():
    direct = score_policy_theme_runner_archetype(_cluster("QBIT", "QBIT receives direct CHIPS Act government funding award for quantum systems today"), _overlay("QBIT"))
    stale = score_policy_theme_runner_archetype(_cluster("OLDQ", "OLDQ was yesterday prior winner already ran on old government funding news"), _overlay("OLDQ"))
    mega = score_policy_theme_runner_archetype(_cluster("NVDA", "NVDA mentioned as broad AI semiconductor sympathy peer in sector basket without direct award"), _overlay("NVDA", gap=3.0))
    indirect = score_policy_theme_runner_archetype(_cluster("PEER", "PEER mentioned alongside quantum sector basket sympathy without direct benefit"), _overlay("PEER", gap=8.0))

    assert direct["policy_theme_runner_score"] >= 5.5
    assert "POLICY_THEME_RUNNER_ARCHETYPE" in direct["tags"]
    assert stale["policy_theme_runner_score"] < direct["policy_theme_runner_score"]
    assert "STALE_PRIOR_WINNER" in stale["tags"]
    assert mega["policy_theme_runner_score"] < direct["policy_theme_runner_score"]
    assert indirect["policy_theme_runner_score"] < direct["policy_theme_runner_score"]


def test_source_lane_status_writes_required_lanes_and_alias_fields(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    rows = build_source_lane_status(
        [
            {
                "source_name": "government_scout",
                "ticker_candidates": ["INFQ", "QBTS"],
                "official_flag": True,
                "structured_flag": False,
                "social_flag": False,
            }
        ],
        primary_ticker="INFQ",
    )
    assert [row["lane_name"] for row in rows] == REQUIRED_SOURCE_LANES
    government = next(row for row in rows if row["lane_name"] == "SAM.gov/USAspending")
    assert government["produced_candidates_count"] == 2
    assert government["produced_candidates"] == 2
    assert government["candidate_count"] == 2
    assert government["affected_primary_selection"] is True
    assert government["useful_for_primary"] is True


def test_premarket_market_closed_report_still_contains_post_audit_fields(monkeypatch, tmp_path):
    storage = premarket_pipeline.ResearchRunStorage(root=tmp_path / "run", trading_day="2026-05-22")
    monkeypatch.setattr(premarket_pipeline, "_today_storage", lambda: storage)
    monkeypatch.setattr(premarket_pipeline, "load_live_config", lambda: {"session": {"timezone": "America/New_York"}})
    monkeypatch.setattr(premarket_pipeline, "load_workflow_config", lambda: {"workflow": {"watchlist": {}}})
    monkeypatch.setattr(
        premarket_pipeline,
        "_market_session_snapshot",
        lambda cfg: {"ok": True, "is_open": False, "same_day_session_ahead": False, "next_open": "2026-05-26T09:30:00-04:00", "market_closed_for_day": True},
    )

    report = premarket_pipeline.build_premarket_report()

    for key in [
        "research_leader",
        "executable_primary",
        "watch_only",
        "second_leg_watch",
        "no_trade_extended",
        "anti_chase_state",
        "opportunity_lifecycle_state",
        "entry_viability_score",
        "same_style_backup_status",
        "backup_pool_diagnostics",
        "source_lane_status",
    ]:
        assert key in report
    assert len(report["source_lane_status"]) == len(REQUIRED_SOURCE_LANES)


def test_stream_required_failure_rejects_skipped_or_empty_stream():
    module = _load_script("scripts/run_next_open_shadow_validation.py")
    assert module._stream_required_failure({"reason": "stream_skipped"}, stream_required=True) is True
    assert module._stream_required_failure({"stream_capture_started": True, "stream_capture_completed": True, "stream_captured": True, "raw_quote_count": 1, "raw_trade_count": 1, "decision_count": 1, "orders_submitted": False}, stream_required=True) is False
    assert module._stream_required_failure({"stream_capture_started": True, "stream_capture_completed": True, "stream_captured": True, "raw_quote_count": 1, "raw_trade_count": 0, "decision_count": 1, "orders_submitted": False}, stream_required=True) is True
    assert module._stream_required_failure({"stream_capture_started": True, "stream_capture_completed": True, "stream_captured": True, "raw_quote_count": 1, "raw_trade_count": 1, "decision_count": 1, "orders_submitted": True}, stream_required=True) is True


def test_captured_infq_continuation_replay_builds_buy_now_artifact(tmp_path):
    module = _load_script("scripts/replay_infq_continuation.py")
    input_dir = ROOT / "reports/live_monitor/runs/opening_stream_2026-05-22_132548"
    if not input_dir.exists():
        return

    summary = module.replay_continuation(input_dir, tmp_path, symbol="INFQ")

    assert summary["orders_submitted"] is False
    assert summary["proposal_count"] >= 1
    assert summary["whether_0946_style_move_was_caught"] is True
    assert summary["best_decision"]["decision"]["action"] == "BUY_NOW"
    written = json.loads((tmp_path / "final_summary.json").read_text())
    assert written["continuation_monitor_started"] is True
