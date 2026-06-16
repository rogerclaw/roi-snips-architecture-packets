from src.ops.artifact_gate import evaluate_artifact_gate
from src.research.war_room import run_candidate_tournament
from src.strategy.momentum_router import route_momentum_strategy
from src.workflows.clean_rebuild import run_clean_rebuild_shadow


def test_tournament_blocks_stale_winner_and_boring_mega_cap() -> None:
    result = run_candidate_tournament(
        [
            {
                "ticker": "INFQ",
                "catalyst": "yesterday winner recycling old move",
                "evidence_score": 8,
                "momentum_score": 8,
                "asymmetry_score": 8,
                "freshness_score": 3,
                "market_cap_bucket": "micro",
                "prior_winner": True,
            },
            {
                "ticker": "AMD",
                "catalyst": "generic analyst note",
                "evidence_score": 6,
                "momentum_score": 5,
                "asymmetry_score": 3,
                "freshness_score": 6,
                "market_cap_bucket": "mega",
            },
            {
                "ticker": "ABCD",
                "catalyst": "fresh FDA clearance plus social velocity",
                "evidence_score": 7,
                "momentum_score": 8,
                "asymmetry_score": 9,
                "freshness_score": 9,
                "market_cap_bucket": "micro",
                "official_source_count": 1,
                "social_velocity_score": 8,
            },
        ]
    )

    assert result["best_pick"] == "ABCD"
    assert result["stale_winner_blocked"] is True
    assert result["mega_cap_fallback_blocked"] is True


def test_momentum_router_covers_opening_vwap_orb_second_leg_and_event_modes() -> None:
    route = route_momentum_strategy(
        {"ticker": "ABCD", "gap_pct": 12},
        {"minutes_from_open": 12, "above_vwap": True, "opening_range_break": True, "event_minutes": 5},
    )

    assert route["broker_action"] == "NONE"
    assert "VWAP_RECLAIM_LONG" in route["allowed_modes"]
    assert "ORB_BREAK_LONG" in route["allowed_modes"]
    assert "SECOND_LEG_CONTINUATION_LONG" in route["allowed_modes"]
    assert "EVENT_TIMED_MOMENTUM_LONG" in route["allowed_modes"]


def test_artifact_gate_prevents_false_readiness_without_no_order_attestation() -> None:
    gate = evaluate_artifact_gate({"candidate_tournament": {"best_pick": "ABCD"}})

    assert gate.ready is False
    assert "missing_brokerless_no_order_attestation" in gate.blockers
    assert "broad_discovery" in gate.missing_artifacts


def test_artifact_gate_blocks_false_readiness_without_strategy_mode() -> None:
    gate = evaluate_artifact_gate(
        {
            "morning_control_plane": {"brokerless_shadow_only": True},
            "broad_discovery": {"candidate_count": 1},
            "research_war_room": {"best_pick": "ABCD"},
            "candidate_tournament": {
                "best_pick": "ABCD",
                "stale_winner_blocked": True,
                "mega_cap_fallback_blocked": True,
            },
            "catalyst_strategy_router": {"allowed_modes": [], "broker_action": "NONE"},
            "opening_bell_engine": {"broker_action": "NONE"},
            "continuation_engine": {"broker_action": "NONE"},
            "event_timed_engine": {"broker_action": "NONE"},
            "execution_plan": {"broker_action": "NONE"},
            "post_miss_learning": {"broker_action": "NONE"},
            "no_order_attestation": {"brokerless": True, "orders_submitted": False},
        }
    )

    assert gate.ready is False
    assert "strategy_router_returned_no_allowed_modes" in gate.blockers


def test_clean_rebuild_shadow_is_brokerless_and_ready_with_complete_artifacts() -> None:
    result = run_clean_rebuild_shadow(
        [
            {
                "ticker": "ABCD",
                "catalyst": "fresh contract award",
                "evidence_score": 8,
                "momentum_score": 8,
                "asymmetry_score": 8,
                "freshness_score": 9,
                "market_cap_bucket": "small",
                "official_source_count": 1,
            }
        ],
        {"minutes_from_open": 2, "gap_pct": 9},
    )

    assert result["ready"] is True
    assert result["artifact_gate"]["no_order_attestation"] is True
    assert result["artifacts"]["no_order_attestation"]["orders_submitted"] is False
    assert result["artifacts"]["catalyst_strategy_router"]["primary_mode"] == "OPENING_BURST_HYPER_LONG"
    assert result["artifacts"]["morning_control_plane"]["brokerless_shadow_only"] is True
    assert result["artifacts"]["opening_bell_engine"]["broker_action"] == "NONE"


def test_clean_rebuild_artifact_gate_requires_full_control_plane() -> None:
    gate = evaluate_artifact_gate(
        {
            "broad_discovery": {"candidate_count": 1},
            "candidate_tournament": {
                "best_pick": "ABCD",
                "stale_winner_blocked": True,
                "mega_cap_fallback_blocked": True,
            },
            "no_order_attestation": {"brokerless": True, "orders_submitted": False},
        }
    )

    assert gate.ready is False
    assert "morning_control_plane" in gate.missing_artifacts
    assert "catalyst_strategy_router" in gate.missing_artifacts
    assert "post_miss_learning" in gate.missing_artifacts


def test_tournament_prefers_no_trade_over_weak_candidates() -> None:
    result = run_candidate_tournament(
        [
            {
                "ticker": "EFGH",
                "catalyst": "thin rumor",
                "evidence_score": 2,
                "momentum_score": 3,
                "asymmetry_score": 3,
                "freshness_score": 4,
                "market_cap_bucket": "small",
            }
        ]
    )

    assert result["best_pick"] is None
    assert result["no_trade"] is True
    assert "below_hyper_trade_threshold" in result["no_trade_reasons"]


def test_rebuild_prompt_pack_and_report_exist() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    prompt_dir = root / "docs" / "prompts" / "rebuild"
    expected = [
        "00_MASTER_MISSION.md",
        "01_RAW_DISCOVERY_QUERY_GENERATION.md",
        "02_BROAD_PRO_STYLE_DISCOVERY.md",
        "03_EVIDENCE_PACKET_BUILDER.md",
        "04_SOCIAL_NARRATIVE_VELOCITY.md",
        "05_THEME_WAVE.md",
        "06_CATALYST_TIMING.md",
        "07_ANTI_CHASE_STALE_WINNER.md",
        "08_CANDIDATE_TOURNAMENT.md",
        "09_EXECUTION_STRATEGY_ROUTER.md",
        "10_OPENING_BURST.md",
        "11_SECOND_LEG_ORB_VWAP.md",
        "12_EVENT_TIMED_CATALYST.md",
        "13_ADVERSARIAL_RED_TEAM.md",
        "14_FINAL_PACKET_GENERATOR.md",
        "15_POST_MISS_AUDIT.md",
    ]

    for filename in expected:
        body = (prompt_dir / filename).read_text()
        assert body.startswith("#")
        assert len(body.split()) >= 20

    report = root / "reports" / "implementation" / "ROI_SNIPS_CLEAN_REBUILD_IMPLEMENTATION_REPORT_2026-05-28.txt"
    report_body = report.read_text()
    assert "216 passed" in report_body
    assert "Live arming is not recommended" in report_body
    assert "Slice 2/3 conformance patch" in report_body
