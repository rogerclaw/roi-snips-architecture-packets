from src.strategy.strategy_router import route_strategy, runbook_strategy_modes


def test_router_exposes_every_slice4_runbook_mode() -> None:
    modes = set(runbook_strategy_modes())

    assert {
        "OPENING_BURST_HYPER_LONG",
        "GAP_AND_GO_CONFIRMATION",
        "PREMARKET_HIGH_RECLAIM",
        "VWAP_WASHOUT_RECLAIM",
        "ORB_BREAK_1MIN",
        "ORB_BREAK_5MIN",
        "SECOND_LEG_CONTINUATION",
        "EVENT_TIMED_HEADLINE_REACTION",
        "EVENT_PREPOSITION_STARTER",
        "NEWS_RELEASE_SCALP",
        "HALT_REOPEN_REACTION",
        "NO_TRADE_WAIT",
    }.issubset(modes)


def test_router_routes_opening_and_event_without_broker_action() -> None:
    route = route_strategy(
        {"ticker": "ABCD", "gap_pct": 8},
        {
            "minutes_from_open": 1,
            "opening_drive_score": 8.7,
            "price_above_open": True,
            "event_minutes": 5,
        },
        event={"minutes_from_event": 5, "news_release": True},
    )

    assert "OPENING_BURST_HYPER_LONG" in route.allowed_modes
    assert "GAP_AND_GO_CONFIRMATION" in route.allowed_modes
    assert "EVENT_TIMED_HEADLINE_REACTION" in route.allowed_modes
    assert "NEWS_RELEASE_SCALP" in route.allowed_modes
    assert route.broker_action == "NONE"
    assert route.order_intent == "SIGNAL_ONLY"
    assert route.order_type == "AGGRESSIVE_LIMIT_ONLY"


def test_router_blocks_entry_without_exit_manager() -> None:
    route = route_strategy(
        {"ticker": "ABCD", "gap_pct": 9},
        {"minutes_from_open": 2, "opening_drive_score": 9, "price_above_open": True},
        has_exit_manager=False,
    )

    assert route.allowed_modes == ["NO_TRADE_WAIT"]
    assert route.primary_mode == "NO_TRADE_WAIT"
    assert "missing_exit_manager" in route.blockers
    assert route.exit_manager_required is True
    assert route.exit_manager_present is False
    assert route.broker_action == "NONE"


def test_post_1100_stream_is_connectivity_only_not_market_open_ready() -> None:
    route = route_strategy(
        {"ticker": "ABCD", "gap_pct": 7},
        {"minutes_from_open": 91, "opening_range_break": True, "orb_5min_breakout": True},
    )

    assert route.proof_scope == "CONNECTIVITY_ONLY"
    assert route.market_open_ready is False
    assert route.allowed_modes == ["NO_TRADE_WAIT"]
    assert "post_1100_stream_connectivity_only" in route.warnings


def test_router_routes_continuation_family_before_1100() -> None:
    route = route_strategy(
        {"ticker": "ABCD"},
        {
            "minutes_from_open": 35,
            "vwap_washout_reclaim_confirmed": True,
            "orb_1min_breakout": True,
            "orb_5min_breakout": True,
        },
    )

    assert "VWAP_WASHOUT_RECLAIM" in route.allowed_modes
    assert "ORB_BREAK_1MIN" in route.allowed_modes
    assert "ORB_BREAK_5MIN" in route.allowed_modes
    assert "SECOND_LEG_CONTINUATION" in route.allowed_modes
