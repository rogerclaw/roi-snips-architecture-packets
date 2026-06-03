from pathlib import Path

from src.execution.order_router import OrderRouter
from src.execution.proposal_store import save_proposal


class StubTradeAdapter:
    def __init__(self, environment="live"):
        self.environment = environment
        self.previewed_orders = []
        self.placed_orders = []
        self.position_calls = 0
        self.open_order_calls = 0
        self.account_calls = 0

    def preview_order(self, order):
        self.previewed_orders.append(order)
        return {"ok": True, "preview_id": "pv1", "order": order}

    def place_order(self, order):
        self.placed_orders.append(order)
        return {"ok": True, "broker_order_id": "ord1", "order": order}

    def cancel_order(self, broker_order_id):
        return {"ok": True, "broker_order_id": broker_order_id}

    def query_order(self, broker_order_id):
        return {"ok": True, "broker_order_id": broker_order_id}

    def list_positions(self):
        self.position_calls += 1
        return {"ok": True, "positions": []}

    def list_open_orders(self, limit=50):
        self.open_order_calls += 1
        return {"ok": True, "orders": []}

    def get_account(self):
        self.account_calls += 1
        return {"ok": True, "account": {"cash": "100000", "buying_power": "100000"}}

    def runtime_environment(self):
        return {"provider": "alpaca", "environment": self.environment, "base_url": "https://paper-api.alpaca.markets" if self.environment == "paper" else "https://api.alpaca.markets"}


class RuntimeFailingTradeAdapter(StubTradeAdapter):
    def __init__(self):
        super().__init__(environment="live")
        self.placed = False

    def runtime_environment(self):
        raise RuntimeError("broker runtime unavailable")

    def place_order(self, order):
        self.placed = True
        return super().place_order(order)


class NoAccountTradeAdapter:
    def __init__(self):
        self.inner = StubTradeAdapter(environment="live")
        self.previewed_orders = self.inner.previewed_orders
        self.placed_orders = self.inner.placed_orders

    def preview_order(self, order):
        return self.inner.preview_order(order)

    def place_order(self, order):
        return self.inner.place_order(order)

    def list_positions(self):
        return self.inner.list_positions()

    def list_open_orders(self, limit=50):
        return self.inner.list_open_orders(limit=limit)

    def runtime_environment(self):
        return self.inner.runtime_environment()


class EmptyAccountTradeAdapter(StubTradeAdapter):
    def get_account(self):
        self.account_calls += 1
        return {"ok": True, "account": {}}


def _cfg(tmp_path: Path):
    return {
        "strategy": {"max_open_positions": 1},
        "risk": {
            "initial_notional_usd_min": 50,
            "initial_notional_usd_max": 100,
            "max_trade_risk_usd": 25,
            "max_spread_bps": 35,
            "max_slippage_bps": 20,
        },
        "session": {
            "timezone": "America/New_York",
            "first_new_entry_et": "00:00",
            "last_new_entry_et": "23:59",
            "force_flat_all_et": "23:59",
        },
        "controls": {
            "live_armed_file": str(tmp_path / "LIVE_ARMED"),
            "kill_switch_file": str(tmp_path / "KILL_SWITCH"),
            "disable_entries_file": str(tmp_path / "DISABLE_NEW_ENTRIES"),
            "proposals_dir": str(tmp_path / "proposals"),
            "operator_events_dir": str(tmp_path / "operator_events"),
            "telegram_offset_file": str(tmp_path / "telegram_offset.txt"),
        },
    }


def _write_ticket(tmp_path: Path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM"):
    import json

    ticket = {
        "status": "AUTHORIZED",
        "authorizer": "openai_deep_mini",
        "authorized_ticker": ticker,
        "authorized_strategy": strategy,
        "completed_before_deadline": True,
        "deep_research_completed": True,
        "deep_research_artifacts": {"final_packet": "final.json"},
        "deterministic_fallback_executable_allowed": False,
        "backup_execution_allowed": False,
        "same_style_backup_pool_ok": True,
        "exceptional_mega_cap_test_passed": ticker in {"NVDA", "AMD", "TSLA", "AAPL", "AMZN", "META", "MSFT", "GOOG", "GOOGL", "NFLX", "PLTR", "QQQ", "SMCI", "SPY"},
    }
    ticket_path = tmp_path / "ticket.json"
    gate_path = tmp_path / "final_gate.json"
    ticket_path.write_text(json.dumps(ticket))
    gate_path.write_text(json.dumps({"readiness_status": "GREEN", "verdict": "GO", "armed_live": True}))
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(ticket_path))
    monkeypatch.setenv("ROI_SNIPS_FINAL_ARMING_GATE_PATH", str(gate_path))
    return ticket


def test_submit_order_dry_run_without_human_approval(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "false")
    router = OrderRouter(trade_adapter=StubTradeAdapter(), cfg=cfg)
    proposal = {
        "plan_id": "plan_test_1",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "ORB_BREAK",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert result["ok"]
    assert result["mode"] == "dry_run"
    assert result["preview"]["ok"]


def test_submit_order_live_when_armed(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    router = OrderRouter(trade_adapter=StubTradeAdapter(environment="live"), cfg=cfg)
    proposal = {
        "plan_id": "plan_test_2",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert result["ok"]
    assert result["mode"] == "live"
    assert result["placement"]["ok"]


def test_live_submission_blocks_market_order_type_before_preview_or_place(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = StubTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_market_block",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
        "order_type": "MARKET",
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert not result["ok"]
    assert result["reason"] == "market_order_not_allowed"
    assert adapter.placed_orders == []


def test_live_submission_sentinel_blocks_second_order(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = StubTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    first = {
        "plan_id": "plan_first",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    second = {**first, "plan_id": "plan_second", "ticker": "AMD"}
    save_proposal(first, cfg)
    save_proposal(second, cfg)

    first_result = router.submit_order(first)
    second_result = router.submit_order(second)
    assert first_result["ok"]
    assert not second_result["ok"]
    assert second_result["reason"] == "existing_position_or_order_blocker:pending_submission"
    assert len(adapter.placed_orders) == 1


def test_live_submission_fails_closed_without_account_lookup(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = NoAccountTradeAdapter()
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_missing_account_lookup",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)

    assert not result["ok"]
    assert result["reason"] == "account_state_unavailable"
    assert adapter.previewed_orders == []
    assert adapter.placed_orders == []


def test_live_submission_fails_closed_with_empty_cash_state(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = EmptyAccountTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_empty_cash_state",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)

    assert not result["ok"]
    assert result["reason"] == "cash_state_unavailable"
    assert adapter.previewed_orders == []
    assert adapter.placed_orders == []


def test_off_guard_files_do_not_block_live_submission(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    Path(cfg["controls"]["kill_switch_file"]).write_text("OFF\n")
    Path(cfg["controls"]["disable_entries_file"]).write_text("OFF\n")
    router = OrderRouter(trade_adapter=StubTradeAdapter(environment="live"), cfg=cfg)
    proposal = {
        "plan_id": "plan_test_3",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert result["ok"]
    assert result["mode"] == "live"
    assert result["placement"]["ok"]


def test_live_submission_blocks_when_live_armed_file_missing(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = StubTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_test_live_missing",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert not result["ok"]
    assert result["reason"] == "live_armed_missing"
    assert adapter.previewed_orders == []
    assert adapter.placed_orders == []


def test_live_submission_blocks_before_preview_when_live_armed_missing(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = StubTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_live_armed_missing_pre_preview",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)

    assert result["ok"] is False
    assert result["reason"] == "live_armed_missing"
    assert adapter.previewed_orders == []
    assert adapter.placed_orders == []


def test_submit_order_paper_when_paper_armed(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cfg["broker"] = {"environment": "paper"}
    monkeypatch.delenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", raising=False)
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="ORB_BREAK")
    router = OrderRouter(trade_adapter=StubTradeAdapter(environment="paper"), cfg=cfg)
    proposal = {
        "plan_id": "plan_test_4",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "ORB_BREAK",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert result["ok"]
    assert result["mode"] == "paper"
    assert result["placement"]["ok"]


def test_paper_arm_fails_closed_on_live_broker(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cfg["broker"] = {"environment": "paper"}
    monkeypatch.delenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", raising=False)
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "true")
    router = OrderRouter(trade_adapter=StubTradeAdapter(environment="live"), cfg=cfg)
    proposal = {
        "plan_id": "plan_test_5",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "ORB_BREAK",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert not result["ok"]
    assert result["reason"] == "paper_submission_requires_paper_broker"


def test_live_opening_order_requires_exit_manager_armed(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    router = OrderRouter(trade_adapter=StubTradeAdapter(environment="live"), cfg=cfg)
    proposal = {
        "plan_id": "plan_exit_manager_missing",
        "ticker": "INFQ",
        "direction": "LONG",
        "trigger": "OPENING_BURST_HYPER_LONG",
        "mode": "OPENING_BURST_HYPER_LONG",
        "entry": 10.0,
        "stop": 9.75,
        "target_1": 10.75,
        "shares": 5,
        "notional_usd": 50.0,
        "max_risk_usd": 1.25,
        "spread_bps": 20.0,
        "max_slippage_bps": 20.0,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert not result["ok"]
    assert result["reason"] == "opening_exit_manager_not_armed"


def test_live_submission_fails_closed_when_runtime_environment_unavailable(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    adapter = RuntimeFailingTradeAdapter()
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_runtime_unavailable",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)
    assert not result["ok"]
    assert result["reason"] == "live_submission_runtime_unavailable"
    assert adapter.placed is False


def test_live_submission_requires_callable_account_probe_before_preview(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = NoAccountTradeAdapter()
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_no_account_probe",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)

    assert not result["ok"]
    assert result["reason"] == "account_state_unavailable"
    assert adapter.previewed_orders == []
    assert adapter.placed_orders == []


def test_live_submission_requires_parseable_cash_before_preview(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    _write_ticket(tmp_path, monkeypatch, ticker="NVDA", strategy="VWAP_RECLAIM")
    adapter = EmptyAccountTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_empty_account",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "VWAP_RECLAIM",
        "entry": 100.0,
        "stop": 99.5,
        "target_1": 101.0,
        "shares": 1,
        "notional_usd": 100.0,
        "max_risk_usd": 0.5,
        "spread_bps": 10.0,
        "max_slippage_bps": 20.0,
        "opening_exit_manager_armed": True,
    }
    save_proposal(proposal, cfg)

    result = router.submit_order(proposal)

    assert not result["ok"]
    assert result["reason"] == "cash_state_unavailable"
    assert adapter.previewed_orders == []
    assert adapter.placed_orders == []
