from datetime import datetime, timezone

from src.workflows import live_monitor


class StubMD:
    def get_quote(self, symbol):
        return {
            "ok": True,
            "quote": {
                "last": 10.5,
                "bid": 10.49,
                "ask": 10.51,
                "prev_close": 10.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def get_bars_1m(self, symbol, limit=240):
        return {"ok": True, "bars": [{"timestamp": datetime.now(timezone.utc).isoformat(), "close": 10.5, "volume": 1000}]}


class StubNotifier:
    def configured(self):
        return False

    def send(self, text):
        raise AssertionError("send should not be called when unconfigured")


class StubPositionManager:
    def __init__(self, *args, **kwargs):
        pass

    def count_open_positions(self):
        return {"ok": True, "count": 0, "positions": []}


class InfqContinuationStubMD:
    def get_quote(self, symbol):
        return {
            "ok": True,
            "quote": {
                "last": 16.42,
                "bid": 16.4,
                "ask": 16.44,
                "prev_close": 11.29,
                "timestamp": "2026-05-22T13:46:00+00:00",
                "spread_bps": 24,
            },
        }

    def get_bars_1m(self, symbol, limit=240):
        bars = [
            {"timestamp": "2026-05-22T13:20:00+00:00", "open": 15.4, "high": 16.12, "low": 15.2, "close": 16.0, "volume": 600000},
            {"timestamp": "2026-05-22T13:30:00+00:00", "open": 16.0, "high": 16.22, "low": 15.9, "close": 16.1, "volume": 500000},
            {"timestamp": "2026-05-22T13:31:00+00:00", "open": 16.1, "high": 16.18, "low": 15.95, "close": 16.05, "volume": 250000},
            {"timestamp": "2026-05-22T13:32:00+00:00", "open": 16.05, "high": 16.16, "low": 15.96, "close": 16.0, "volume": 230000},
            {"timestamp": "2026-05-22T13:33:00+00:00", "open": 16.0, "high": 16.2, "low": 15.98, "close": 16.08, "volume": 240000},
            {"timestamp": "2026-05-22T13:34:00+00:00", "open": 16.08, "high": 16.25, "low": 16.0, "close": 16.12, "volume": 240000},
            {"timestamp": "2026-05-22T13:35:00+00:00", "open": 16.12, "high": 16.15, "low": 15.98, "close": 16.0, "volume": 180000},
            {"timestamp": "2026-05-22T13:36:00+00:00", "open": 16.0, "high": 16.08, "low": 15.94, "close": 15.95, "volume": 160000},
            {"timestamp": "2026-05-22T13:37:00+00:00", "open": 15.95, "high": 16.05, "low": 15.94, "close": 15.98, "volume": 150000},
            {"timestamp": "2026-05-22T13:38:00+00:00", "open": 15.98, "high": 16.06, "low": 15.95, "close": 16.02, "volume": 140000},
            {"timestamp": "2026-05-22T13:39:00+00:00", "open": 16.02, "high": 16.08, "low": 15.97, "close": 16.0, "volume": 150000},
            {"timestamp": "2026-05-22T13:40:00+00:00", "open": 16.0, "high": 16.08, "low": 15.96, "close": 15.98, "volume": 160000},
            {"timestamp": "2026-05-22T13:41:00+00:00", "open": 15.98, "high": 16.08, "low": 15.97, "close": 16.0, "volume": 170000},
            {"timestamp": "2026-05-22T13:42:00+00:00", "open": 16.0, "high": 16.1, "low": 15.99, "close": 16.05, "volume": 180000},
            {"timestamp": "2026-05-22T13:43:00+00:00", "open": 16.05, "high": 16.14, "low": 16.02, "close": 16.08, "volume": 190000},
            {"timestamp": "2026-05-22T13:44:00+00:00", "open": 16.08, "high": 16.16, "low": 16.04, "close": 16.1, "volume": 200000},
            {"timestamp": "2026-05-22T13:45:00+00:00", "open": 16.1, "high": 16.22, "low": 16.06, "close": 16.18, "volume": 210000},
            {"timestamp": "2026-05-22T13:46:00+00:00", "open": 16.18, "high": 16.44, "low": 16.12, "close": 16.42, "volume": 350000},
        ]
        return {"ok": True, "bars": bars}


def _patch_common(monkeypatch, *, submission_mode: str):
    cfg = {
        "strategy": {"max_open_positions": 1},
        "market_data": {"max_quote_age_ms_open": 999999},
        "session": {"timezone": "America/New_York"},
    }
    monkeypatch.setattr(live_monitor, "load_live_config", lambda: cfg)
    monkeypatch.setattr(live_monitor, "active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "force_flat": False, "in_entry_window": True})
    monkeypatch.setattr(live_monitor, "session_phase", lambda cfg: "ENTRY_WINDOW")
    monkeypatch.setattr(live_monitor, "should_force_flat", lambda cfg: False)
    monkeypatch.setattr(live_monitor, "_load_opening_drive_state", lambda path: {})
    monkeypatch.setattr(live_monitor, "_load_authorized_trade_ticket", lambda repo_root: {
        "status": "AUTHORIZED",
        "authorized_ticker": "MRAM",
        "authorized_strategy": "ORB_BREAK",
        "authorizer": "openai_deep_mini",
        "expires_at": "2099-01-01T14:30:00Z",
        "backup_execution_allowed": False,
        "backup_tickers_authorized_for_live": [],
    })
    monkeypatch.setattr(live_monitor, "_save_opening_drive_state", lambda path, payload: None)
    monkeypatch.setattr(live_monitor, "_load_active_watchlist", lambda repo_root: [{"symbol": "MRAM", "catalyst_type": "contract"}])
    monkeypatch.setattr(live_monitor, "build_market_data_adapter", lambda cfg: StubMD())
    monkeypatch.setattr(live_monitor, "PositionManager", StubPositionManager)
    monkeypatch.setattr(live_monitor, "TelegramNotifier", StubNotifier)
    monkeypatch.setattr(
        live_monitor,
        "_build_structured_candidate",
        lambda symbol_row, phase, quote, bars, cfg, open_positions: {"ticker": "MRAM", "trigger": "ORB_BREAK", "mode": "ORB_BREAK", "strategy_family": "CatalystContinuationLong", "shares": 5, "entry": 10.5, "stop": 9.9, "target_1": 11.3, "opening_exit_manager_armed": True},
    )
    monkeypatch.setattr(live_monitor, "build_trade_proposal", lambda candidate: {**candidate, "plan_id": "plan-1", "ticker": candidate["ticker"], "hard_max_entry_price": 10.52})
    monkeypatch.setattr(live_monitor, "validate_trade_plan", lambda proposal, risk_cfg: (True, None))
    monkeypatch.setattr(live_monitor, "find_recent_matching_proposal", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_monitor, "save_proposal", lambda proposal, cfg: None)

    class StubRouter:
        def __init__(self, cfg=None):
            self.cfg = cfg

        def submission_mode(self):
            return submission_mode

        def _live_enabled(self):
            return submission_mode == "live"

        def submit_order(self, plan):
            return {"ok": True, "mode": submission_mode, "placement": {"broker_order_id": "abc123"}}

    monkeypatch.setattr(live_monitor, "OrderRouter", StubRouter)


def test_no_order_continuation_monitor_arms_infq_orb_break_after_0935(monkeypatch):
    cfg = {
        "strategy": {"max_open_positions": 1},
        "risk": {
            "initial_notional_usd_min": 50,
            "initial_notional_usd_max": 1000,
            "max_trade_risk_usd": 80,
            "max_spread_bps": 60,
            "max_slippage_bps": 30,
            "continuation_max_chase_pct": 3.0,
        },
        "market_data": {"max_quote_age_ms_open": 9999999999},
        "session": {"timezone": "America/New_York"},
    }
    monkeypatch.setattr(live_monitor, "load_live_config", lambda: cfg)
    monkeypatch.setattr(live_monitor, "active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "force_flat": False, "in_entry_window": True})
    monkeypatch.setattr(live_monitor, "session_phase", lambda cfg: "ENTRY_WINDOW")
    monkeypatch.setattr(live_monitor, "should_force_flat", lambda cfg: False)
    monkeypatch.setattr(live_monitor, "_load_opening_drive_state", lambda path: {})
    monkeypatch.setattr(live_monitor, "_load_authorized_trade_ticket", lambda repo_root: {
        "status": "AUTHORIZED",
        "authorized_ticker": "INFQ",
        "authorized_strategy": "ORB_BREAK_LONG",
        "authorizer": "openai_deep_mini",
        "expires_at": "2099-01-01T14:30:00Z",
        "backup_execution_allowed": False,
        "backup_tickers_authorized_for_live": [],
    })
    monkeypatch.setattr(live_monitor, "_save_opening_drive_state", lambda path, payload: None)
    monkeypatch.setattr(
        live_monitor,
        "_load_active_watchlist",
        lambda repo_root: [{
            "symbol": "INFQ",
            "catalyst_type": "government_contract",
            "catalyst_notes": ["validated CHIPS funding catalyst"],
            "premarket_high": 16.12,
            "spread_bps": 24,
            "research_conviction_score": 92,
            "attention_ignition_score": 88,
            "pre_move_asymmetry_score": 91,
            "execution_safety_score": 82,
            "live_validation_score": 89,
            "why_tradeable": "validated catalyst runner reset after the opening burst and reclaimed the opening range",
        }],
    )
    monkeypatch.setattr(live_monitor, "build_market_data_adapter", lambda cfg: InfqContinuationStubMD())
    monkeypatch.setattr(live_monitor, "PositionManager", StubPositionManager)
    monkeypatch.setattr(live_monitor, "TelegramNotifier", StubNotifier)
    monkeypatch.setattr(live_monitor, "find_recent_matching_proposal", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_monitor, "save_proposal", lambda proposal, cfg: None)
    monkeypatch.setattr(live_monitor, "append_audit_event", lambda *args, **kwargs: None)

    class DryRunRouter:
        def __init__(self, cfg=None):
            self.cfg = cfg

        def submission_mode(self):
            return "dry_run"

        def _live_enabled(self):
            return False

    monkeypatch.setattr(live_monitor, "OrderRouter", DryRunRouter)

    result = live_monitor.run_live_monitor_once()

    assert result["status"] == "arm"
    assert result["live_order_submission_enabled"] is False
    proposal = result["proposals"][0]
    assert proposal["ticker"] == "INFQ"
    assert proposal["mode"] == "ORB_BREAK_LONG"
    assert proposal["trigger"] == "ORB_BREAK"
    assert proposal["signal_context"]["phase"] == "ENTRY_WINDOW"
    assert proposal["signal_context"]["lifecycle_state"] == "OPENING_CONTINUATION_ACTIVE"
    assert proposal["signal_context"]["secondary_lifecycle_state"] == "SECOND_LEG_CONTINUATION_ACTIVE"
    assert proposal["signal_context"]["second_leg_decision"]["action"] == "BUY_NOW"
    assert "submission" not in proposal


def test_no_order_continuation_shadow_skips_broker_state(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "false")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setenv("ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW", "true")
    cfg = {
        "strategy": {"max_open_positions": 1},
        "risk": {
            "initial_notional_usd_min": 50,
            "initial_notional_usd_max": 1000,
            "max_trade_risk_usd": 80,
            "max_spread_bps": 60,
            "max_slippage_bps": 30,
            "continuation_max_chase_pct": 3.0,
        },
        "market_data": {"max_quote_age_ms_open": 9999999999},
        "session": {"timezone": "America/New_York"},
    }
    monkeypatch.setattr(live_monitor, "load_live_config", lambda: cfg)
    monkeypatch.setattr(live_monitor, "active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "force_flat": False, "in_entry_window": True})
    monkeypatch.setattr(live_monitor, "session_phase", lambda cfg: "ENTRY_WINDOW")
    monkeypatch.setattr(live_monitor, "should_force_flat", lambda cfg: False)
    monkeypatch.setattr(live_monitor, "_load_opening_drive_state", lambda path: {})
    monkeypatch.setattr(live_monitor, "_load_authorized_trade_ticket", lambda repo_root: {
        "status": "AUTHORIZED",
        "authorized_ticker": "INFQ",
        "authorized_strategy": "ORB_BREAK_LONG",
        "authorizer": "openai_deep_mini",
        "expires_at": "2099-01-01T14:30:00Z",
        "backup_execution_allowed": False,
        "backup_tickers_authorized_for_live": [],
    })
    monkeypatch.setattr(live_monitor, "_save_opening_drive_state", lambda path, payload: None)
    monkeypatch.setattr(
        live_monitor,
        "_load_active_watchlist",
        lambda repo_root: [{
            "symbol": "INFQ",
            "catalyst_type": "government_contract",
            "catalyst_notes": ["validated CHIPS funding catalyst"],
            "premarket_high": 16.12,
            "spread_bps": 24,
            "research_conviction_score": 92,
            "attention_ignition_score": 88,
            "pre_move_asymmetry_score": 91,
            "execution_safety_score": 82,
            "live_validation_score": 89,
            "why_tradeable": "validated catalyst runner reset after the opening burst and reclaimed the opening range",
        }],
    )
    monkeypatch.setattr(live_monitor, "build_market_data_adapter", lambda cfg: InfqContinuationStubMD())
    monkeypatch.setattr(live_monitor, "PositionManager", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("broker positions should not be queried")))
    monkeypatch.setattr(live_monitor, "OrderRouter", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("order router should not be constructed")))
    monkeypatch.setattr(live_monitor, "TelegramNotifier", StubNotifier)
    monkeypatch.setattr(live_monitor, "find_recent_matching_proposal", lambda *args, **kwargs: None)
    monkeypatch.setattr(live_monitor, "save_proposal", lambda proposal, cfg: None)
    monkeypatch.setattr(live_monitor, "append_audit_event", lambda *args, **kwargs: None)

    result = live_monitor.run_live_monitor_once()

    assert result["status"] == "arm"
    assert result["broker_submission_mode"] == "dry_run"
    assert result["broker_state_mode"] == "brokerless_no_order_shadow"
    assert result["live_order_submission_enabled"] is False
    assert result["paper_order_submission_enabled"] is False
    assert "submission" not in result["proposals"][0]


def test_live_monitor_auto_submits_when_live_armed(monkeypatch):
    _patch_common(monkeypatch, submission_mode="live")
    result = live_monitor.run_live_monitor_once()
    assert result["status"] == "submitted_live"
    assert result["live_order_submission_enabled"] is True
    assert result["proposals"][0]["submission"]["ok"] is True


def test_live_monitor_arms_without_submission_when_live_disarmed(monkeypatch):
    _patch_common(monkeypatch, submission_mode="dry_run")
    result = live_monitor.run_live_monitor_once()
    assert result["status"] == "arm"
    assert result["live_order_submission_enabled"] is False
    assert "submission" not in result["proposals"][0]


def test_live_monitor_disarms_when_live_armed_missing(monkeypatch):
    _patch_common(monkeypatch, submission_mode="live")
    monkeypatch.setattr(live_monitor, "active_guards", lambda cfg: {"live_armed": False, "kill_switch": False, "disable_entries": False, "force_flat": False, "in_entry_window": True})
    result = live_monitor.run_live_monitor_once()
    assert result["status"] == "disarm"
    assert result["reason"] == "live_armed_missing"


def test_live_monitor_auto_submits_when_paper_armed(monkeypatch):
    _patch_common(monkeypatch, submission_mode="paper")
    result = live_monitor.run_live_monitor_once()
    assert result["status"] == "submitted_paper"
    assert result["paper_order_submission_enabled"] is True
    assert result["broker_submission_mode"] == "paper"


def test_build_structured_candidate_supports_opening_drive():
    cfg = {
        "session": {"timezone": "America/New_York"},
        "strategy": {
            "opening_drive": {
                "enabled": True,
                "entry_start_et": "09:30:00",
                "entry_cutoff_et": "09:34:59",
                "min_regular_bars": 1,
                "require_premarket_reference": True,
                "min_first_minute_volume": 150000,
                "min_first_minute_dollar_volume": 750000,
                "min_close_in_range_pct": 0.6,
                "max_chase_pct_above_reference": 1.0,
                "max_spread_bps": 35,
                "max_slippage_bps": 18,
                "risk_budget_usd": 40,
                "notional_cap_usd": 500,
                "time_stop_et": "09:45:00",
            }
        },
        "risk": {
            "initial_notional_usd_min": 50,
            "initial_notional_usd_max": 1000,
            "max_trade_risk_usd": 80,
            "max_spread_bps": 60,
            "opening_drive_max_spread_bps": 35,
            "opening_drive_max_slippage_bps": 18,
            "opening_drive_max_trade_risk_usd": 40,
            "opening_drive_notional_usd_max": 500,
            "opening_drive_min_first_minute_volume": 150000,
            "opening_drive_min_first_minute_dollar_volume": 750000,
            "opening_drive_max_chase_pct": 1.0,
            "opening_drive_min_close_in_range_pct": 0.6,
        },
        "market_data": {},
    }
    symbol_row = {
        "symbol": "MRAM",
        "catalyst_type": "contract",
        "catalyst_notes": ["contract award"],
        "spread_bps": 20,
        "why_tradeable": "fresh catalyst and opening demand",
    }
    quote = {
        "last": 10.08,
        "bid": 10.07,
        "ask": 10.09,
        "timestamp": "2026-05-01T13:31:10+00:00",
    }
    bars = [
        {"timestamp": "2026-05-01T13:20:00+00:00", "open": 9.8, "high": 10.0, "low": 9.75, "close": 9.95, "volume": 50000},
        {"timestamp": "2026-05-01T13:30:00+00:00", "open": 10.0, "high": 10.1, "low": 9.99, "close": 10.06, "volume": 180000},
    ]

    candidate = live_monitor._build_structured_candidate(symbol_row, "ENTRY_WINDOW", quote, bars, cfg, open_positions=0)
    assert candidate is not None
    assert candidate["trigger"] == "OPENING_DRIVE_LONG"
    assert candidate["time_stop"] == "09:45:00"


def test_build_structured_candidate_ignores_prior_day_intraday_bars():
    cfg = {
        "session": {"timezone": "America/New_York"},
        "strategy": {
            "opening_drive": {
                "enabled": True,
                "entry_start_et": "09:30:00",
                "entry_cutoff_et": "09:34:59",
                "min_regular_bars": 1,
                "require_premarket_reference": False,
                "min_first_minute_volume": 150000,
                "min_first_minute_dollar_volume": 750000,
                "min_close_in_range_pct": 0.6,
                "max_chase_pct_above_reference": 1.0,
                "max_spread_bps": 35,
            }
        },
        "risk": {"initial_notional_usd_min": 50, "initial_notional_usd_max": 1000, "max_trade_risk_usd": 80, "opening_drive_notional_usd_max": 500},
        "market_data": {},
    }
    symbol_row = {"symbol": "MRAM", "catalyst_type": "contract", "spread_bps": 20}
    quote = {"last": 10.08, "bid": 10.07, "ask": 10.09, "timestamp": "2026-05-01T13:31:10+00:00"}
    bars = [
        {"timestamp": "2026-04-30T13:30:00+00:00", "open": 20.0, "high": 22.0, "low": 19.0, "close": 21.0, "volume": 900000},
        {"timestamp": "2026-05-01T13:30:00+00:00", "open": 10.0, "high": 10.1, "low": 9.99, "close": 10.06, "volume": 180000},
    ]
    candidate = live_monitor._build_structured_candidate(symbol_row, "ENTRY_WINDOW", quote, bars, cfg, open_positions=0)
    assert candidate is not None
    assert candidate["signal_context"]["first_minute_high"] == 10.1


def test_build_structured_candidate_supports_subminute_opening_drive():
    cfg = {
        "session": {"timezone": "America/New_York"},
        "strategy": {
            "opening_drive": {
                "enabled": True,
                "entry_start_et": "09:30:00",
                "entry_cutoff_et": "09:34:59",
                "min_regular_bars": 1,
                "require_premarket_reference": True,
                "min_first_minute_volume": 150000,
                "min_first_minute_dollar_volume": 750000,
                "min_close_in_range_pct": 0.6,
                "max_chase_pct_above_reference": 1.0,
                "max_spread_bps": 35,
                "max_slippage_bps": 18,
                "risk_budget_usd": 40,
                "notional_cap_usd": 500,
                "time_stop_et": "09:45:00",
                "subminute": {
                    "enabled": True,
                    "entry_cutoff_et": "09:30:55",
                    "min_quote_samples": 3,
                    "min_elapsed_seconds": 10,
                    "min_projected_first_minute_volume": 150000,
                    "min_projected_first_minute_dollar_volume": 750000,
                    "min_close_in_range_pct": 0.75,
                    "max_pullback_from_high_pct": 0.35,
                    "min_push_from_first_sample_pct": 0.15,
                    "min_break_above_reference_bps": 5,
                    "min_hold_pct_of_subminute_high": 0.9975,
                },
            }
        },
        "risk": {
            "initial_notional_usd_min": 50,
            "initial_notional_usd_max": 1000,
            "max_trade_risk_usd": 80,
            "max_spread_bps": 60,
            "opening_drive_max_spread_bps": 35,
            "opening_drive_max_slippage_bps": 18,
            "opening_drive_max_trade_risk_usd": 40,
            "opening_drive_notional_usd_max": 500,
            "opening_drive_min_first_minute_volume": 150000,
            "opening_drive_min_first_minute_dollar_volume": 750000,
            "opening_drive_max_chase_pct": 1.0,
            "opening_drive_min_close_in_range_pct": 0.6,
        },
        "market_data": {},
    }
    symbol_row = {
        "symbol": "MRAM",
        "catalyst_type": "contract",
        "catalyst_notes": ["contract award"],
        "spread_bps": 18,
        "why_tradeable": "fresh catalyst and opening demand",
        "_opening_drive_tape": {
            "bucket": "2026-05-01T09:30",
            "samples": [
                {"timestamp": "2026-05-01T13:30:00+00:00", "last": 10.01, "spread_bps": 18},
                {"timestamp": "2026-05-01T13:30:06+00:00", "last": 10.05, "spread_bps": 18},
                {"timestamp": "2026-05-01T13:30:12+00:00", "last": 10.08, "spread_bps": 17},
            ],
        },
    }
    quote = {
        "last": 10.08,
        "bid": 10.07,
        "ask": 10.09,
        "timestamp": "2026-05-01T13:30:12+00:00",
        "spread_bps": 18,
    }
    bars = [
        {"timestamp": "2026-05-01T13:20:00+00:00", "open": 9.8, "high": 10.0, "low": 9.75, "close": 9.95, "volume": 50000},
        {"timestamp": "2026-05-01T13:30:00+00:00", "open": 10.0, "high": 10.09, "low": 10.0, "close": 10.08, "volume": 35000},
    ]

    candidate = live_monitor._build_structured_candidate(symbol_row, "ENTRY_WINDOW", quote, bars, cfg, open_positions=0)
    assert candidate is not None
    assert candidate["trigger"] == "OPENING_DRIVE_LONG"
    assert candidate["subminute_signal"] is True
    assert candidate["subminute_quote_samples"] == 3
