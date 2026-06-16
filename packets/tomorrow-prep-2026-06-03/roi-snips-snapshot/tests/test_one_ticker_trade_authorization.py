import json
from datetime import datetime, timezone

from src.research.storage import ResearchRunStorage
from src.research.trade_authorization import authorize_one_ticker_trade
from src.workflows import live_monitor, opening_bell_monitor, opening_stream_supervisor, premarket_pipeline


def test_internal_fallback_never_gets_live_trade_authorization() -> None:
    auth = authorize_one_ticker_trade(
        {"best_pick": "NVDA", "source_mode": "internal_fallback"},
        deep_mini_required=True,
        deep_mini_completed=True,
        same_style_backup_pool_ok=True,
        executable_primary={"symbol": "NVDA"},
    )

    assert auth.authorized is False
    assert auth.ticker is None
    assert "not_governed_deep_mini_selection" in auth.blockers


def test_grok_governed_packet_cannot_get_live_trade_authorization() -> None:
    auth = authorize_one_ticker_trade(
        {"best_pick": "ABCD", "source_mode": "governed_grok_d_research"},
        deep_mini_required=True,
        deep_mini_completed=True,
        same_style_backup_pool_ok=True,
        executable_primary={"symbol": "ABCD"},
    )

    assert auth.authorized is False
    assert "not_governed_deep_mini_selection" in auth.blockers


def test_mega_cap_requires_explicit_exceptional_authorization() -> None:
    auth = authorize_one_ticker_trade(
        {"best_pick": "NVDA", "source_mode": "governed_deep_mini"},
        deep_mini_required=True,
        deep_mini_completed=True,
        same_style_backup_pool_ok=True,
        executable_primary={"symbol": "NVDA"},
    )

    assert auth.authorized is False
    assert "mega_cap_requires_explicit_exceptional_test" in auth.blockers


def test_same_style_backup_failure_blocks_authorized_primary() -> None:
    auth = authorize_one_ticker_trade(
        {"best_pick": "ABCD", "source_mode": "governed_deep_mini"},
        deep_mini_required=True,
        deep_mini_completed=True,
        same_style_backup_pool_ok=False,
        executable_primary={"symbol": "ABCD"},
    )

    assert auth.authorized is False
    assert "same_style_backup_pool_not_green" in auth.blockers


def test_premarket_report_nulls_executable_when_authorization_fails(tmp_path, monkeypatch) -> None:
    storage = ResearchRunStorage(root=tmp_path / "run", trading_day="2026-05-29")
    monkeypatch.setattr(premarket_pipeline, "_today_storage", lambda: storage)
    monkeypatch.setattr(premarket_pipeline, "load_live_config", lambda: {"research_mode": {"deep_mini_required_for_live_research": True}})
    monkeypatch.setattr(premarket_pipeline, "load_workflow_config", lambda: {"workflow": {"watchlist": {"tier_count": {"A": 2, "B": 4, "C": 4}}}})
    monkeypatch.setattr(
        premarket_pipeline,
        "_market_session_snapshot",
        lambda cfg, **kwargs: {"ok": True, "is_open": False, "same_day_session_ahead": True, "next_open": "2026-05-29T09:30:00-04:00", "market_closed_for_day": False},
    )
    row = {
        "ticker": "NVDA",
        "cluster": {"primary_ticker": "NVDA", "company_name": "Nvidia", "catalyst_type_primary": "generic_ai", "claim_summary": "Generic AI sympathy"},
        "research_scorecard": {"catalyst_strength_score": 7, "freshness_score": 9, "attention_acceleration_score": 8, "crowding_score": 3, "official_confirmation_count": 1, "structured_confirmation_count": 1, "social_confirmation_count": 1, "story_stage": "early"},
        "research_priority_score": 8,
        "hyper_trade_score": 8,
        "lane_tags": [],
        "execution_gate": {"passed": True, "execution_readiness_score": 90, "blockers": [], "warnings": []},
        "overlay": {
            "ticker": "NVDA",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "gap_pct": 7,
            "last_premarket_price": 200,
            "premarket_dollar_volume": 1000000,
            "estimated_spread_pct": 0.1,
            "execution_readiness_score": 90,
            "execution_blockers": [],
            "execution_warnings": [],
            "anti_chase_state": "PREMARKET_BUILDING",
            "opportunity_lifecycle_state": "PREMARKET_BUILDING",
            "entry_viability_score": 72,
        },
    }
    storage.write_json("meta/run_manifest.json", {"mode": "research_v2", "generated_at_utc": "2026-05-29T13:00:00+00:00", "artifacts": {"deep_mini_run": {"success": True}}})
    storage.write_json("normalized/discovered_symbols.json", ["NVDA"])
    storage.write_json("normalized/research_ranked_candidates.json", [row])
    storage.write_json("normalized/execution_eligible_candidates.json", [row])
    storage.write_json("normalized/execution_blocked_candidates.json", [])
    storage.write_json("normalized/daily_best_pick_packet.json", {"best_pick": "NVDA", "source_mode": "governed_deep_mini", "deep_mini_artifact_status": {"completed": True}})
    storage.write_json("overlays/market_overlay.json", {"NVDA": row["overlay"]})

    report = premarket_pipeline.build_premarket_report()

    assert report["status"] == "NO_TRADE_RESEARCH_INCOMPLETE"
    assert report["best_pick_candidate"] is None
    assert report["executable_primary"] is None
    assert report["trade_authorization"]["authorized"] is False
    assert "mega_cap_requires_explicit_exceptional_test" in report["trade_authorization"]["blockers"]


def test_opening_bell_readiness_requires_one_ticker_authorization(monkeypatch) -> None:
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": True}})
    monkeypatch.setattr(
        opening_bell_monitor,
        "_latest_morning_packet",
        lambda root: {
            "best_pick": {"ticker": "ABCD"},
            "deep_mini_required_for_live_research": True,
            "deep_mini_shortlist_status": "completed",
            "deep_mini_completed_before_deadline": True,
            "trade_authorization": {"authorized": False, "ticker": None, "blockers": ["same_style_backup_pool_not_green"]},
        },
    )
    monkeypatch.setattr(opening_bell_monitor, "build_live_readiness_report", lambda cfg, **kwargs: {"execution_blockers": [], "full_execution_ready": True})

    result = opening_bell_monitor.check_opening_bell_readiness()

    assert result["status"] == "RED"
    assert "no_valid_trade_authorization_ticket" in result["opening_bell_blockers"]


def _write_valid_ticket(root, ticker="ABCD") -> None:
    ticket_dir = root / "runs" / datetime.now().strftime("%Y-%m-%d")
    ticket_dir.mkdir(parents=True)
    ticket_dir.joinpath("trade_authorization_ticket.json").write_text(
        json.dumps(
            {
                "status": "AUTHORIZED",
                "authorizer": "openai_deep_mini",
                "authorized_ticker": ticker,
                "authorized_strategy": "ORB_BREAK",
                "completed_before_deadline": True,
                "deep_research_completed": True,
                "deep_research_artifacts": {"final_packet": "final.json"},
                "deterministic_fallback_executable_allowed": False,
                "backup_execution_allowed": False,
                "same_style_backup_pool_ok": True,
            }
        )
    )


def test_live_monitor_watchlist_uses_only_ticket_authorized_primary(tmp_path, monkeypatch) -> None:
    day = datetime.now().strftime("%Y-%m-%d")
    report_dir = tmp_path / "reports" / "morning" / "json"
    report_dir.mkdir(parents=True)
    (report_dir / f"{day}.json").write_text(
        """
{
  "deep_mini_required_for_live_research": true,
  "trade_authorization": {"authorized": true, "ticker": "ABCD"},
  "best_pick_candidate": {"symbol": "ABCD"},
  "watchlist": {"A": [{"symbol": "NVDA"}], "B": [{"symbol": "TSLA"}]}
}
""".strip()
    )
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(tmp_path / "runs" / day / "trade_authorization_ticket.json"))
    _write_valid_ticket(tmp_path)

    rows = live_monitor._load_active_watchlist(tmp_path)

    assert [row["symbol"] for row in rows] == ["ABCD"]
    assert rows[0]["trade_authorization_ticket"]["authorized_ticker"] == "ABCD"


def test_live_monitor_watchlist_rejects_morning_authorization_without_ticket(tmp_path, monkeypatch) -> None:
    day = datetime.now().strftime("%Y-%m-%d")
    report_dir = tmp_path / "reports" / "morning" / "json"
    report_dir.mkdir(parents=True)
    (report_dir / f"{day}.json").write_text(
        """
{
  "deep_mini_required_for_live_research": true,
  "trade_authorization": {"authorized": true, "ticker": "ABCD"},
  "best_pick_candidate": {"symbol": "ABCD"},
  "watchlist": {"A": [{"symbol": "NVDA"}], "B": [{"symbol": "TSLA"}]}
}
""".strip()
    )
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(tmp_path / "missing_ticket.json"))

    assert live_monitor._load_active_watchlist(tmp_path) == []


def test_opening_stream_morning_candidates_drop_watchlist_fallbacks(tmp_path, monkeypatch) -> None:
    day = datetime.now().strftime("%Y-%m-%d")
    report_dir = tmp_path / "reports" / "morning" / "json"
    report_dir.mkdir(parents=True)
    (report_dir / f"{day}.json").write_text(
        """
{
  "deep_mini_required_for_live_research": true,
  "trade_authorization": {"authorized": true, "ticker": "ABCD"},
  "best_pick_candidate": {"symbol": "ABCD", "hyper_trade_score": 9},
  "watchlist": {"A": [{"symbol": "NVDA", "hyper_trade_score": 9}], "B": [{"symbol": "TSLA"}]},
  "candidate_research_packets": []
}
""".strip()
    )
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(tmp_path / "runs" / day / "trade_authorization_ticket.json"))
    _write_valid_ticket(tmp_path)
    monkeypatch.setattr(opening_stream_supervisor, "repo_root", lambda: tmp_path)

    rows = opening_stream_supervisor._load_morning_candidates()

    assert [row["symbol"] for row in rows] == ["ABCD"]


def test_opening_stream_morning_candidates_reject_packet_without_ticket(tmp_path, monkeypatch) -> None:
    day = datetime.now().strftime("%Y-%m-%d")
    report_dir = tmp_path / "reports" / "morning" / "json"
    report_dir.mkdir(parents=True)
    (report_dir / f"{day}.json").write_text(
        """
{
  "deep_mini_required_for_live_research": true,
  "trade_authorization": {"authorized": true, "ticker": "ABCD"},
  "best_pick_candidate": {"symbol": "ABCD", "hyper_trade_score": 9},
  "watchlist": {"A": [{"symbol": "NVDA", "hyper_trade_score": 9}], "B": [{"symbol": "TSLA"}]},
  "candidate_research_packets": []
}
""".strip()
    )
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(tmp_path / "missing_ticket.json"))
    monkeypatch.setattr(opening_stream_supervisor, "repo_root", lambda: tmp_path)

    assert opening_stream_supervisor._load_morning_candidates() == []
