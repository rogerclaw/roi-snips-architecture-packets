import json
from datetime import datetime, timedelta, timezone

from src.research.storage import ResearchRunStorage
from src.workflows import premarket_pipeline
from src.workflows.premarket_pipeline import _tier_watchlist


def test_market_session_snapshot_uses_clock_source_when_execution_broker_is_webull(monkeypatch):
    class StubClock:
        def get_clock(self):
            return {
                "ok": True,
                "clock": {
                    "timestamp": "2026-06-03T08:00:00-04:00",
                    "is_open": False,
                    "next_open": "2026-06-03T09:30:00-04:00",
                    "next_close": "2026-06-03T16:00:00-04:00",
                },
            }

    monkeypatch.setattr(premarket_pipeline, "AlpacaClockAdapter", StubClock)

    snapshot = premarket_pipeline._market_session_snapshot({"broker": {"provider": "webull"}})

    assert snapshot["ok"]
    assert snapshot["same_day_session_ahead"] is True


def test_build_premarket_report_reuses_fresh_cached_overlays(tmp_path, monkeypatch):
    storage = ResearchRunStorage(root=tmp_path / "run", trading_day="2026-04-30")
    monkeypatch.setattr(premarket_pipeline, "_today_storage", lambda: storage)
    monkeypatch.setattr(premarket_pipeline, "load_live_config", lambda: {"session": {"timezone": "America/New_York"}})
    monkeypatch.setattr(premarket_pipeline, "load_workflow_config", lambda: {"workflow": {"watchlist": {"tier_count": {"A": 1, "B": 1, "C": 2}}}})
    monkeypatch.setattr(
        premarket_pipeline,
        "_market_session_snapshot",
        lambda cfg: {"ok": True, "is_open": False, "same_day_session_ahead": True, "next_open": "2026-04-30T09:30:00-04:00", "market_closed_for_day": False},
    )

    storage.write_json("meta/run_manifest.json", {"mode": "research_v2", "generated_at_utc": "2026-04-30T13:20:00+00:00", "artifacts": {"deep_mini_run": {"success": True}}})
    storage.write_json("normalized/discovered_symbols.json", ["MRAM"])
    ranked = [{
        "ticker": "MRAM",
        "cluster": {"primary_ticker": "MRAM", "company_name": "Everspin", "catalyst_type_primary": "product_or_partnership", "claim_summary": "MRAM wins contract"},
        "research_scorecard": {"catalyst_strength_score": 5.8, "freshness_score": 8.6, "attention_acceleration_score": 3.1, "crowding_score": 2.0, "official_confirmation_count": 0, "structured_confirmation_count": 1, "social_confirmation_count": 0, "story_stage": "early"},
        "research_priority_score": 6.4,
        "story_stage": "early",
        "execution_gate": {"passed": True, "execution_readiness_score": 74.0, "blockers": [], "warnings": []},
    }]
    storage.write_json("normalized/research_ranked_candidates.json", ranked)
    storage.write_json("normalized/execution_eligible_candidates.json", ranked)
    storage.write_json("normalized/execution_blocked_candidates.json", [])
    storage.write_json("normalized/daily_best_pick_packet.json", {"best_pick": "MRAM", "source_mode": "governed_deep_mini"})
    storage.write_json(
        "overlays/market_overlay.json",
        {
            "MRAM": {
                "ticker": "MRAM",
                "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "last_premarket_price": 11.2,
                "gap_pct": 7.1,
                "premarket_volume": 120000,
                "premarket_dollar_volume": 1300000,
                "estimated_spread_pct": 0.28,
                "execution_readiness_score": 74.0,
                "execution_blockers": [],
                "execution_warnings": [],
            }
        },
    )

    def fail_build(*args, **kwargs):
        raise AssertionError("build_market_overlays should not be called when cache is fresh")

    monkeypatch.setattr(premarket_pipeline, "build_market_overlays", fail_build)
    report = premarket_pipeline.build_premarket_report()
    assert report["best_pick_candidate"]["symbol"] == "MRAM"
    assert report["best_pick_candidate"]["last_price"] == 11.2
    assert report["sources"]["overlay_cache"]["count"] == 1


def test_write_report_honors_report_trading_date(tmp_path, monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_TRADE_DATE", "2026-05-29")
    report = {
        "generated_at_utc": "2026-05-29T12:00:00+00:00",
        "status": "NO_TRADE_RESEARCH_INCOMPLETE",
        "trading_date": "2026-05-29",
        "market_session": {},
        "best_pick_candidate": None,
        "research_leader": None,
        "executable_primary": None,
        "watchlist": {"A": [], "B": [], "C": []},
        "no_trade_list": [],
        "sources": {},
    }

    json_path, md_path = premarket_pipeline.write_report(report, tmp_path)

    assert json_path.name == "2026-05-29.json"
    assert md_path.name == "2026-05-29.md"


def test_build_premarket_report_fails_closed_when_market_closed(monkeypatch):
    monkeypatch.setattr(premarket_pipeline, "load_live_config", lambda: {"session": {"timezone": "America/New_York"}})
    monkeypatch.setattr(premarket_pipeline, "load_workflow_config", lambda: {"workflow": {"watchlist": {"tier_count": {"A": 1, "B": 1, "C": 2}}}})
    monkeypatch.setattr(
        premarket_pipeline,
        "_market_session_snapshot",
        lambda cfg: {
            "ok": True,
            "timestamp": "2026-05-02T09:04:17-04:00",
            "is_open": False,
            "same_day_session_ahead": False,
            "next_open": "2026-05-04T09:30:00-04:00",
            "next_close": "2026-05-04T16:00:00-04:00",
            "market_closed_for_day": True,
        },
    )

    class FailPipeline:
        def __init__(self, *args, **kwargs):
            raise AssertionError("ResearchPipeline should not run when market is closed for the day")

    monkeypatch.setattr(premarket_pipeline, "ResearchPipeline", FailPipeline)
    report = premarket_pipeline.build_premarket_report()
    assert report["status"] == "market_closed"
    assert report["best_pick_candidate"] is None
    assert report["watchlist"] == {"A": [], "B": [], "C": []}
    assert report["no_trade_list"][0]["symbol"] == "MARKET"
    assert "2026-05-04" in report["no_trade_list"][0]["reason"]


def test_build_premarket_report_does_not_promote_blocked_research_leader(tmp_path, monkeypatch):
    storage = ResearchRunStorage(root=tmp_path / "run", trading_day="2026-04-30")
    monkeypatch.setattr(premarket_pipeline, "_today_storage", lambda: storage)
    monkeypatch.setattr(premarket_pipeline, "load_live_config", lambda: {"session": {"timezone": "America/New_York"}})
    monkeypatch.setattr(premarket_pipeline, "load_workflow_config", lambda: {"workflow": {"watchlist": {"tier_count": {"A": 1, "B": 1, "C": 2}}}})
    monkeypatch.setattr(
        premarket_pipeline,
        "_market_session_snapshot",
        lambda cfg: {"ok": True, "is_open": False, "same_day_session_ahead": True, "next_open": "2026-04-30T09:30:00-04:00", "market_closed_for_day": False},
    )

    ranked = [{
        "ticker": "MRAM",
        "cluster": {"primary_ticker": "MRAM", "company_name": "Everspin", "catalyst_type_primary": "product_or_partnership", "claim_summary": "MRAM wins contract"},
        "research_scorecard": {"catalyst_strength_score": 5.8, "freshness_score": 8.6, "attention_acceleration_score": 3.1, "crowding_score": 2.0, "official_confirmation_count": 0, "structured_confirmation_count": 1, "social_confirmation_count": 0, "story_stage": "early"},
        "research_priority_score": 6.4,
        "story_stage": "early",
        "execution_gate": {"passed": False, "execution_readiness_score": 0.0, "blockers": ["spread_estimate_missing"], "warnings": []},
    }]
    storage.write_json("meta/run_manifest.json", {"mode": "research_v2", "generated_at_utc": "2026-04-30T13:20:00+00:00"})
    storage.write_json("normalized/discovered_symbols.json", ["MRAM"])
    storage.write_json("normalized/research_ranked_candidates.json", ranked)
    storage.write_json("normalized/execution_eligible_candidates.json", [])
    storage.write_json("normalized/execution_blocked_candidates.json", ranked)
    storage.write_json(
        "normalized/daily_best_pick_packet.json",
        {"best_pick": None, "research_leader": "MRAM", "source_mode": "internal_fallback", "caveats": ["no_execution_eligible_candidate"]},
    )
    storage.write_json("overlays/market_overlay.json", {})

    report = premarket_pipeline.build_premarket_report()
    assert report["status"] == "degraded"
    assert report["best_pick_candidate"] is None
    assert report["watchlist"]["A"] == []
    assert report["watchlist"]["B"][0]["symbol"] == "MRAM"


def test_tier_watchlist_dedupes_symbols_across_tiers():
    research = [
        {"ticker": "INFQ", "cluster": {"primary_ticker": "INFQ"}},
        {"ticker": "INFQ", "cluster": {"primary_ticker": "INFQ"}},
        {"ticker": "MRAM", "cluster": {"primary_ticker": "MRAM"}},
    ]
    execution = [
        {"ticker": "INFQ", "cluster": {"primary_ticker": "INFQ"}},
        {"ticker": "INFQ", "cluster": {"primary_ticker": "INFQ"}},
    ]

    tiers = _tier_watchlist(research, execution, {"tier_count": {"A": 3, "B": 3, "C": 3}})

    assert [row["ticker"] for row in tiers["A"]] == ["INFQ"]
    assert [row["ticker"] for row in tiers["B"]] == ["MRAM"]
    assert tiers["C"] == []


def test_extended_policy_runner_is_research_leader_not_executable_primary(tmp_path, monkeypatch):
    storage = ResearchRunStorage(root=tmp_path / "run", trading_day="2026-05-22")
    monkeypatch.setattr(premarket_pipeline, "_today_storage", lambda: storage)
    monkeypatch.setattr(premarket_pipeline, "load_live_config", lambda: {"session": {"timezone": "America/New_York"}})
    monkeypatch.setattr(premarket_pipeline, "load_workflow_config", lambda: {"workflow": {"watchlist": {"tier_count": {"A": 2, "B": 4, "C": 4}}}})
    monkeypatch.setattr(
        premarket_pipeline,
        "_market_session_snapshot",
        lambda cfg: {"ok": True, "is_open": False, "same_day_session_ahead": True, "next_open": "2026-05-22T09:30:00-04:00", "market_closed_for_day": False},
    )
    ranked = [{
        "ticker": "INFQ",
        "cluster": {"primary_ticker": "INFQ", "company_name": "Infleqtion", "catalyst_type_primary": "government_contract", "claim_summary": "INFQ receives CHIPS government funding LOI"},
        "research_scorecard": {"catalyst_strength_score": 8.0, "freshness_score": 9.0, "attention_acceleration_score": 8.0, "crowding_score": 5.0, "official_confirmation_count": 1, "structured_confirmation_count": 2, "social_confirmation_count": 2, "story_stage": "developing", "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"]},
        "research_priority_score": 8.4,
        "hyper_trade_score": 7.1,
        "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE", "VERIFIED_CATALYST_RUNNER"],
        "story_stage": "developing",
        "execution_gate": {"passed": True, "execution_readiness_score": 88.0, "blockers": [], "warnings": []},
    }]
    storage.write_json("meta/run_manifest.json", {"mode": "research_v2", "generated_at_utc": "2026-05-22T13:15:00+00:00"})
    storage.write_json("normalized/discovered_symbols.json", ["INFQ"])
    storage.write_json("normalized/research_ranked_candidates.json", ranked)
    storage.write_json("normalized/execution_eligible_candidates.json", ranked)
    storage.write_json("normalized/execution_blocked_candidates.json", [])
    storage.write_json("normalized/daily_best_pick_packet.json", {"best_pick": "INFQ", "research_leader": "INFQ", "source_mode": "internal_fallback"})
    storage.write_json("normalized/candidate_research_packets.json", [])
    storage.write_json("normalized/source_lane_status.json", [])
    storage.write_json(
        "overlays/market_overlay.json",
        {
            "INFQ": {
                "ticker": "INFQ",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "last_premarket_price": 16.12,
                "gap_pct": 42.9,
                "premarket_volume": 8_770_000,
                "premarket_dollar_volume": 119_980_000,
                "estimated_spread_pct": 0.22,
                "execution_readiness_score": 88.0,
                "execution_blockers": [],
                "execution_warnings": [],
            }
        },
    )

    report = premarket_pipeline.build_premarket_report()

    assert report["research_leader"]["symbol"] == "INFQ"
    assert report["executable_primary"] is None
    assert report["anti_chase_state"] == "SECOND_LEG_WATCH"
    assert report["opportunity_lifecycle_state"] == "SECOND_LEG_WATCH"
    assert report["entry_viability_score"] < 60
    assert report["second_leg_watch"][0]["symbol"] == "INFQ"


def test_validated_extreme_gap_runner_stays_second_leg_watch():
    state = premarket_pipeline.classify_anti_chase_state(
        gap_pct=68.0,
        estimated_spread_pct=0.22,
        premarket_dollar_volume=120_000_000,
        execution_blockers=[],
        catalyst_validated=True,
    )

    assert state["anti_chase_state"] == "SECOND_LEG_WATCH"
    assert state["opportunity_lifecycle_state"] == "SECOND_LEG_WATCH"
    assert state["entry_viability_score"] < 50


def test_unvalidated_extreme_gap_runner_remains_no_trade_extended():
    state = premarket_pipeline.classify_anti_chase_state(
        gap_pct=68.0,
        estimated_spread_pct=0.22,
        premarket_dollar_volume=120_000_000,
        execution_blockers=[],
        catalyst_validated=False,
    )

    assert state["anti_chase_state"] == "NO_TRADE_EXTENDED"
    assert state["opportunity_lifecycle_state"] == "NO_TRADE_EXTENDED"


def test_policy_runner_backup_pool_prioritizes_non_megacap_same_style_names():
    research = [
        {"ticker": "INFQ", "hyper_trade_score": 7.1, "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"], "cluster": {"primary_ticker": "INFQ"}},
        {"ticker": "QBTS", "hyper_trade_score": 4.2, "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"], "cluster": {"primary_ticker": "QBTS"}},
        {"ticker": "RGTI", "hyper_trade_score": 3.9, "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"], "cluster": {"primary_ticker": "RGTI"}},
        {"ticker": "QUBT", "hyper_trade_score": 3.5, "lane_tags": ["POLICY_THEME_RUNNER_ARCHETYPE"], "cluster": {"primary_ticker": "QUBT"}},
        {"ticker": "NVDA", "hyper_trade_score": 4.5, "lane_tags": [], "cluster": {"primary_ticker": "NVDA"}},
    ]
    tiers = _tier_watchlist(research, [research[0]], {"tier_count": {"A": 1, "B": 4, "C": 4}})
    assert [row["ticker"] for row in tiers["B"][:3]] == ["QBTS", "RGTI", "QUBT"]
