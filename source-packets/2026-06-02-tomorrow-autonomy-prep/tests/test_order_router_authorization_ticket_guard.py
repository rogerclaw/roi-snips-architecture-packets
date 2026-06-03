import json
from pathlib import Path

from src.execution.order_router import OrderRouter
from src.execution.proposal_store import save_proposal

from tests.test_order_router import StubTradeAdapter, _cfg
from tests.test_trade_authorization_ticket import valid_ticket


def test_order_router_blocks_unauthorized_ticker_before_preview(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cfg["research_mode"] = {"require_trade_authorization_ticket": True}
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    ticket_path = tmp_path / "ticket.json"
    gate_path = tmp_path / "final_gate.json"
    ticket_path.write_text(json.dumps(valid_ticket("INFQ")))
    gate_path.write_text(json.dumps({"readiness_status": "GREEN", "verdict": "GO", "armed_live": True}))
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(ticket_path))
    monkeypatch.setenv("ROI_SNIPS_FINAL_ARMING_GATE_PATH", str(gate_path))
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    adapter = StubTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_wrong_ticket",
        "trade_date": "2026-05-29",
        "ticker": "NVDA",
        "direction": "LONG",
        "trigger": "ORB_BREAK",
        "mode": "ORB_BREAK",
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
    assert result["reason"] in {"unauthorized_ticker_not_in_deep_research_ticket", "mega_cap_backup_not_authorized"}
    assert adapter.placed_orders == []


def test_order_router_requires_ticket_for_live_even_without_config_flag(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cfg["research_mode"] = {}
    Path(cfg["controls"]["live_armed_file"]).write_text("armed\n")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    adapter = StubTradeAdapter(environment="live")
    router = OrderRouter(trade_adapter=adapter, cfg=cfg)
    proposal = {
        "plan_id": "plan_missing_ticket",
        "trade_date": "2026-05-29",
        "ticker": "INFQ",
        "direction": "LONG",
        "trigger": "ORB_BREAK",
        "mode": "ORB_BREAK",
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
    assert result["reason"] == "no_valid_trade_authorization_ticket"
    assert adapter.placed_orders == []
