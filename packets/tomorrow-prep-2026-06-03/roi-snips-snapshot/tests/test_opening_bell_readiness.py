from datetime import datetime
from zoneinfo import ZoneInfo

from src.workflows import opening_bell_monitor
from src.workflows import final_live_arming_gate


def _valid_ticket(symbol="MRAM"):
    return {
        "status": "AUTHORIZED",
        "authorizer": "openai_deep_mini",
        "authorized_ticker": symbol,
        "authorized_strategy": "ORB_BREAK",
        "completed_before_deadline": True,
        "deep_research_completed": True,
        "deep_research_artifacts": {"final_packet": "final.json"},
        "deterministic_fallback_executable_allowed": False,
        "backup_execution_allowed": False,
        "same_style_backup_pool_ok": True,
    }


def _observed_readiness(observed, payload):
    def inner(ignore_arm_guards=False, **kwargs):
        observed["ignore_arm_guards"] = ignore_arm_guards
        observed["kwargs"] = kwargs
        return payload

    return inner


def test_opening_bell_readiness_yellow_for_expected_fail_closed_guards(monkeypatch):
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": True}})
    monkeypatch.setattr(opening_bell_monitor, "_latest_morning_packet", lambda root: {"best_pick": {"ticker": "MRAM"}})
    monkeypatch.setattr(
        opening_bell_monitor,
        "build_live_readiness_report",
        lambda cfg, **kwargs: {
            "execution_blockers": ["live_armed_missing", "disable_entries_active"],
            "full_execution_ready": False,
            "runtime_guards": {"live_armed": False, "disable_entries": True, "kill_switch": False},
        },
    )
    result = opening_bell_monitor.check_opening_bell_readiness()
    assert result["status"] == "YELLOW"
    assert result["primary_candidate"] == "MRAM"


def test_opening_bell_readiness_can_ignore_arm_guards_for_conditional_arming(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": True}})
    monkeypatch.setattr(opening_bell_monitor, "_latest_morning_packet", lambda root: {"best_pick": {"ticker": "MRAM"}})
    monkeypatch.setattr(opening_bell_monitor, "load_today_ticket", lambda root: _valid_ticket("MRAM"))
    monkeypatch.setattr(
        opening_bell_monitor,
        "build_live_readiness_report",
        lambda cfg, **kwargs: {
            "execution_blockers": ["live_armed_missing", "disable_entries_active"],
            "full_execution_ready": False,
            "runtime_guards": {"live_armed": False, "disable_entries": True, "kill_switch": False},
        },
    )
    monkeypatch.setattr(opening_bell_monitor, "_candidate_specific_readiness", lambda packet, cfg: {"ok": True, "candidates": [{"symbol": "MRAM"}], "blockers": []})
    result = opening_bell_monitor.check_opening_bell_readiness(ignore_arm_guards=True)
    assert result["status"] == "GREEN"
    assert result["ignored_arm_guard_blockers"] == ["disable_entries_active", "live_armed_missing"]


def test_final_live_arming_gate_clears_fail_closed_guards_only_when_green(monkeypatch):
    actions = []
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setattr(final_live_arming_gate, "load_live_config", lambda: {})
    monkeypatch.setattr(final_live_arming_gate, "repo_root", lambda: opening_bell_monitor.repo_root())
    observed = {}
    monkeypatch.setattr(
        final_live_arming_gate,
        "check_opening_bell_readiness",
        _observed_readiness(
            observed,
            {
            "status": "GREEN",
            "opening_bell_blockers": [],
            "ignored_arm_guard_blockers": ["disable_entries_active", "live_armed_missing"],
            "primary_candidate": "MRAM",
            "candidate_specific_readiness": {"ok": True},
            },
        ),
    )
    monkeypatch.setattr(final_live_arming_gate, "activate_flag", lambda name, reason="", cfg=None: actions.append(("activate", name, reason)))
    monkeypatch.setattr(final_live_arming_gate, "clear_flag", lambda name, cfg=None: actions.append(("clear", name, "")))
    monkeypatch.setattr(final_live_arming_gate, "active_guards", lambda cfg, **kwargs: {"live_armed": True, "disable_entries": False, "kill_switch": False})
    monkeypatch.setattr(final_live_arming_gate, "load_today_ticket", lambda root, trade_date=None: _valid_ticket())
    monkeypatch.setattr(final_live_arming_gate, "_deep_mini_reached_blockers", lambda root, trade_date: [])
    monkeypatch.setattr(final_live_arming_gate, "_write_json", lambda path, payload: None)

    result = final_live_arming_gate.run_final_live_arming_gate(execute=True)
    assert result["verdict"] == "GO"
    assert observed["kwargs"]["inspect_broker_state"] is True
    assert result["armed_live"] is True
    assert ("clear", "disable_entries", "") in actions
    assert any(action == "activate" and name == "live_armed" for action, name, reason in actions)


def test_final_live_arming_gate_honors_trade_date_override(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_TRADE_DATE", "2026-05-29")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setattr(final_live_arming_gate, "load_live_config", lambda: {})
    monkeypatch.setattr(final_live_arming_gate, "repo_root", lambda: opening_bell_monitor.repo_root())
    monkeypatch.setattr(
        final_live_arming_gate,
        "check_opening_bell_readiness",
        lambda ignore_arm_guards=False, **kwargs: {
            "status": "GREEN",
            "opening_bell_blockers": [],
            "ignored_arm_guard_blockers": ["disable_entries_active"],
            "primary_candidate": "MRAM",
            "candidate_specific_readiness": {"ok": True},
        },
    )
    monkeypatch.setattr(final_live_arming_gate, "activate_flag", lambda name, reason="", cfg=None: None)
    monkeypatch.setattr(final_live_arming_gate, "clear_flag", lambda name, cfg=None: None)
    monkeypatch.setattr(final_live_arming_gate, "active_guards", lambda cfg, **kwargs: {"live_armed": True, "disable_entries": False, "kill_switch": False})
    monkeypatch.setattr(final_live_arming_gate, "load_today_ticket", lambda root, trade_date=None: _valid_ticket())
    monkeypatch.setattr(final_live_arming_gate, "_deep_mini_reached_blockers", lambda root, trade_date: [])
    monkeypatch.setattr(final_live_arming_gate, "_write_json", lambda path, payload: None)

    result = final_live_arming_gate.run_final_live_arming_gate(execute=True)

    assert result["trade_date"] == "2026-05-29"


def test_final_live_arming_gate_dry_run_skips_broker_state(monkeypatch):
    observed = {}
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setattr(final_live_arming_gate, "load_live_config", lambda: {})
    monkeypatch.setattr(final_live_arming_gate, "repo_root", lambda: opening_bell_monitor.repo_root())
    monkeypatch.setattr(
        final_live_arming_gate,
        "check_opening_bell_readiness",
        _observed_readiness(
            observed,
            {
            "status": "RED",
            "opening_bell_blockers": ["broker_state_inspection_skipped"],
            "ignored_arm_guard_blockers": [],
            "primary_candidate": None,
            "candidate_specific_readiness": {"ok": False},
            },
        ),
    )
    monkeypatch.setattr(final_live_arming_gate, "active_guards", lambda cfg: {"live_armed": False, "disable_entries": True, "kill_switch": False})
    monkeypatch.setattr(final_live_arming_gate, "load_today_ticket", lambda root, trade_date=None: _valid_ticket())
    monkeypatch.setattr(final_live_arming_gate, "_write_json", lambda path, payload: None)

    result = final_live_arming_gate.run_final_live_arming_gate(execute=False)

    assert observed["kwargs"]["inspect_broker_state"] is False
    assert result["verdict"] == "NO_GO"
    assert result["orders_submitted_now"] is False
    assert result["orders_previewed_now"] is False


def test_final_live_arming_gate_holds_fail_closed_when_not_green(monkeypatch):
    actions = []
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setattr(final_live_arming_gate, "load_live_config", lambda: {})
    monkeypatch.setattr(final_live_arming_gate, "repo_root", lambda: opening_bell_monitor.repo_root())
    monkeypatch.setattr(
        final_live_arming_gate,
        "check_opening_bell_readiness",
        lambda ignore_arm_guards=False, **kwargs: {
            "status": "RED",
            "opening_bell_blockers": ["market_data_not_candidate_specific"],
            "ignored_arm_guard_blockers": ["disable_entries_active", "live_armed_missing"],
            "primary_candidate": None,
            "candidate_specific_readiness": {"ok": False},
        },
    )
    monkeypatch.setattr(final_live_arming_gate, "activate_flag", lambda name, reason="", cfg=None: actions.append(("activate", name, reason)))
    monkeypatch.setattr(final_live_arming_gate, "clear_flag", lambda name, cfg=None: actions.append(("clear", name, "")))
    monkeypatch.setattr(final_live_arming_gate, "active_guards", lambda cfg, **kwargs: {"live_armed": False, "disable_entries": True, "kill_switch": False})
    monkeypatch.setattr(final_live_arming_gate, "_write_json", lambda path, payload: None)

    result = final_live_arming_gate.run_final_live_arming_gate(execute=True)
    assert result["verdict"] == "NO_GO"
    assert result["armed_live"] is False
    assert ("clear", "live_armed", "") in actions
    assert any(action == "activate" and name == "disable_entries" for action, name, reason in actions)


def test_opening_bell_readiness_red_when_config_missing_even_if_live_ready(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": False, "reason": "config_missing"}})
    monkeypatch.setattr(opening_bell_monitor, "_latest_morning_packet", lambda root: {"best_pick": {"ticker": "MRAM"}})
    monkeypatch.setattr(
        opening_bell_monitor,
        "build_live_readiness_report",
        lambda cfg, **kwargs: {
            "execution_blockers": [],
            "full_execution_ready": True,
            "runtime_guards": {"live_armed": True, "disable_entries": False, "kill_switch": False},
        },
    )
    monkeypatch.setattr(opening_bell_monitor, "_candidate_specific_readiness", lambda packet, cfg: {"ok": True, "candidates": [], "blockers": []})

    result = opening_bell_monitor.check_opening_bell_readiness()
    assert result["status"] == "RED"
    assert "opening_bell_config_missing" in result["opening_bell_blockers"]


def test_opening_bell_live_readiness_ignores_morning_watchlist_rows(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": True}})
    monkeypatch.setattr(opening_bell_monitor, "_latest_morning_packet", lambda root: {"best_pick": {"ticker": "NVDA"}, "watchlist": {"A": ["bad-row"]}})
    monkeypatch.setattr(opening_bell_monitor, "load_today_ticket", lambda root: _valid_ticket("MRAM"))
    monkeypatch.setattr(opening_bell_monitor, "build_live_readiness_report", lambda cfg, **kwargs: {"execution_blockers": [], "full_execution_ready": True})

    class StubMarketData:
        def get_quote(self, symbol):
            now = datetime.now(ZoneInfo("UTC")).isoformat()
            return {"ok": True, "quote": {"timestamp": now, "bid": 10, "ask": 10.1, "last": 10.05}}

        def get_bars_1m(self, symbol, limit=240):
            now = datetime.now(ZoneInfo("UTC")).isoformat()
            return {"ok": True, "bars": [{"timestamp": now, "close": 10.05, "volume": 1000}]}

    monkeypatch.setattr(opening_bell_monitor, "build_market_data_adapter", lambda cfg, **kwargs: StubMarketData())
    monkeypatch.setattr(opening_bell_monitor, "_mode_diagnostics", lambda row, phase, quote, bars, cfg: {"attempted_modes": [{"failed_predicates": []}]})
    result = opening_bell_monitor.check_opening_bell_readiness()
    assert result["status"] == "GREEN"
    assert result["primary_candidate"] == "MRAM"
    assert result["candidate_specific_readiness"]["candidates"][0]["symbol"] == "MRAM"
    assert "malformed_candidate_row" not in result["opening_bell_blockers"]


def test_opening_bell_live_readiness_rejects_stale_candidate_market_data(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(
        opening_bell_monitor,
        "load_opening_bell_config",
        lambda path=None: {"opening_bell": {"enabled": True, "data": {"max_quote_age_ms": 1000, "max_bar_age_seconds": 90}}},
    )
    monkeypatch.setattr(opening_bell_monitor, "_latest_morning_packet", lambda root: None)
    monkeypatch.setattr(opening_bell_monitor, "load_today_ticket", lambda root: _valid_ticket("MRAM"))
    monkeypatch.setattr(opening_bell_monitor, "build_live_readiness_report", lambda cfg, **kwargs: {"execution_blockers": [], "full_execution_ready": True})

    class StubMarketData:
        def get_quote(self, symbol):
            return {"ok": True, "quote": {"timestamp": "2026-05-21T13:30:00+00:00", "bid": 10, "ask": 10.1, "last": 10.05}}

        def get_bars_1m(self, symbol, limit=240):
            return {"ok": True, "bars": [{"timestamp": "2026-05-21T13:30:00+00:00", "close": 10.05, "volume": 1000}]}

    monkeypatch.setattr(opening_bell_monitor, "build_market_data_adapter", lambda cfg, **kwargs: StubMarketData())
    monkeypatch.setattr(opening_bell_monitor, "_mode_diagnostics", lambda row, phase, quote, bars, cfg: {"attempted_modes": [{"failed_predicates": []}]})

    result = opening_bell_monitor.check_opening_bell_readiness()

    assert result["status"] == "RED"
    assert "MRAM:quote_not_same_trade_date" in result["opening_bell_blockers"]
    assert "MRAM:bar_not_same_trade_date" in result["opening_bell_blockers"]
    assert "MRAM:quote_stale" in result["opening_bell_blockers"]
    assert "MRAM:bar_stale" in result["opening_bell_blockers"]


def test_opening_bell_live_readiness_requires_trade_authorization_ticket(monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setattr(opening_bell_monitor, "load_live_config", lambda: {})
    monkeypatch.setattr(opening_bell_monitor, "load_opening_bell_config", lambda path=None: {"opening_bell": {"enabled": True}})
    monkeypatch.setattr(
        opening_bell_monitor,
        "_latest_morning_packet",
        lambda root: {
            "trade_authorization": {"authorized": True, "ticker": "NVDA"},
            "best_pick": {"ticker": "NVDA"},
        },
    )
    monkeypatch.setattr(opening_bell_monitor, "load_today_ticket", lambda root: None)
    monkeypatch.setattr(opening_bell_monitor, "build_live_readiness_report", lambda cfg, **kwargs: {"execution_blockers": [], "full_execution_ready": True})

    result = opening_bell_monitor.check_opening_bell_readiness(ignore_arm_guards=True)

    assert result["status"] == "RED"
    assert "no_valid_trade_authorization_ticket" in result["opening_bell_blockers"]


def test_hardened_opening_bell_runner_exists_and_prefights_before_loop():
    script = opening_bell_monitor.repo_root() / "scripts" / "run_opening_bell_live_monitor.sh"
    body = script.read_text()
    assert script.exists()
    assert "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" in body
    assert ":-true" in body
    assert "scripts/check_live_readiness.sh" in body
    assert "scripts/check_opening_bell_readiness.sh" in body
    assert "src.workflows.live_monitor" in body
    assert "from src.common.config import load_live_config" in body
    assert "configs/live.yaml" not in body
    assert body.index("scripts/check_live_readiness.sh") < body.index("src.workflows.live_monitor")


def test_streaming_opening_supervisor_script_exists_and_prefights():
    script = opening_bell_monitor.repo_root() / "scripts" / "supervise_opening_bell_live_monitor.sh"
    body = script.read_text()
    assert script.exists()
    assert "PREFLIGHT_ONLY=false" in body
    assert '"${1:-}" = "--preflight-only"' in body
    assert 'mktemp "$TMP_PARENT/roi-snips-opening-readiness.XXXXXXXX.json"' in body
    assert "scripts/check_live_readiness.sh" in body
    assert "scripts/check_opening_bell_readiness.sh" in body
    assert "src.workflows.opening_stream_supervisor" in body
    assert "--live" in body
    assert "--candidates-from-morning" in body
    assert "ROI_SNIPS_RUN_CONTINUATION_MONITOR" in body
    assert 'ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" = "true"' in body
    assert 'RUN_CONTINUATION="false"' in body
    assert "scripts/run_opening_bell_live_monitor.sh --loop-only" in body
    assert "CONTINUATION_PID" in body
    assert body.index("scripts/run_opening_bell_live_monitor.sh --loop-only") < body.index("src.workflows.opening_stream_supervisor")


def test_final_live_arming_gate_script_exists_and_sets_live_env():
    script = opening_bell_monitor.repo_root() / "scripts" / "run_final_live_arming_gate.sh"
    body = script.read_text()
    assert script.exists()
    assert "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true" in body
    assert "ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false" in body
    assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"' in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"' in body
    assert "src.workflows.final_live_arming_gate" in body


def test_no_order_continuation_validation_wrapper_forces_brokerless_shadow_mode():
    script = opening_bell_monitor.repo_root() / "scripts" / "run_no_order_continuation_validation.sh"
    body = script.read_text()
    assert script.exists()
    assert "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false" in body
    assert "ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false" in body
    assert "ROI_SNIPS_RUN_CONTINUATION_MONITOR=true" in body
    assert "ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT=true" in body
    assert "ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW=true" in body
    assert "opening_stream_already_running" in body
    assert "orders_submitted" in body
    assert "src[.]workflows[.]opening_stream_supervisor" in body
    assert "scripts/supervise_opening_bell_live_monitor.sh" in body


def test_streaming_supervisor_can_skip_broker_preflight_only_for_no_order_shadow():
    script = opening_bell_monitor.repo_root() / "scripts" / "supervise_opening_bell_live_monitor.sh"
    body = script.read_text()
    assert "ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT" in body
    assert 'ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" = "false"' in body
    assert "broker_preflight_skipped_for_no_order_market_data_validation" in body
    assert body.index("ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT") < body.index("src.workflows.opening_stream_supervisor")
