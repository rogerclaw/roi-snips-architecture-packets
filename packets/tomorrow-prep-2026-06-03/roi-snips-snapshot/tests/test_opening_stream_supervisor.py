import json

from src.workflows import opening_stream_supervisor
from src.strategy.opening_burst_hyper_long import evaluate_opening_burst_signal
from src.workflows.opening_stream_supervisor import _opening_candidate_from_report_row, replay_opening_stream


CFG = {
    "opening_bell": {
        "data": {"max_quote_age_ms": 1000},
        "thresholds": {
            "first_10s": {"min_hyper_trade_score": 8.0, "min_opening_drive_score": 7.0, "min_volume_burst_score": 6.0},
            "first_30s": {"min_hyper_trade_score": 7.5, "min_opening_drive_score": 7.0, "min_volume_burst_score": 6.0},
            "first_60s": {"min_hyper_trade_score": 7.0, "min_opening_drive_score": 7.0, "min_volume_burst_score": 6.0},
        },
        "order": {"slippage_cap_bps": 20, "slippage_cap_cents": 0.03},
        "sizing": {"verified_default_usd": 300, "verified_strong_usd": 500, "a_plus_max_usd": 1000},
    }
}


def test_stream_replay_writes_raw_logs_and_buy_now_decision(tmp_path):
    candidate = {
        "ticker": "INFQ",
        "hyper_trade_score": 8.8,
        "lane_tags": ["VERIFIED_CATALYST_RUNNER"],
        "entry_cap": 10.7,
        "premarket_high": 10.0,
        "premarket_dollar_volume_per_minute": 100000,
    }
    events = []
    for offset, price in [(0, 10.02), (6, 10.1), (12, 10.2)]:
        events.append({"type": "quote", "symbol": "INFQ", "timestamp": f"2026-05-21T13:30:{offset:02d}+00:00", "bid": price - 0.01, "ask": price + 0.01, "bid_size": 1200, "ask_size": 800})
        events.append({"type": "trade", "symbol": "INFQ", "timestamp": f"2026-05-21T13:30:{offset:02d}+00:00", "price": price, "size": 30000})

    result = replay_opening_stream(candidate, events, CFG, output_dir=tmp_path)

    assert result["status"] == "BUY_NOW"
    assert (tmp_path / "raw_quotes.jsonl").exists()
    assert (tmp_path / "raw_trades.jsonl").exists()
    assert (tmp_path / "opening_tape_features.jsonl").exists()
    assert (tmp_path / "decisions.jsonl").exists()
    assert (tmp_path / "orders.jsonl").exists()
    summary = json.loads((tmp_path / "final_summary.json").read_text())
    assert summary["final_decision"]["action"] == "BUY_NOW"


def test_morning_candidate_uses_per_minute_opening_volume_baseline():
    row = {
        "symbol": "INFQ",
        "hyper_trade_score": 3.775,
        "last_price": 16.12,
        "premarket_dollar_volume": 120_000_000,
        "lane_tags": ["VERIFIED_CATALYST_RUNNER"],
    }
    packet = {
        "ticker": "INFQ",
        "market_snapshot": {"observed_at": "2026-05-22T13:15:00+00:00", "premarket_dollar_volume": 120_000_000},
        "infq_archetype": {"infq_archetype_score": 7.146, "tags": ["INFQ_STYLE_GOVERNMENT_SECTOR_WAVE"]},
        "scorecard": {"lane_tags": ["MOVER_FIRST_EXPLAIN_LATER"]},
    }

    candidate = _opening_candidate_from_report_row(row, packet)

    assert candidate["hyper_trade_score"] == 3.775
    assert candidate["opening_strategy_score"] == 7.146
    assert candidate["infq_archetype_score"] == 7.146
    assert candidate["expected_opening_dollar_volume_60s"] < 500_000
    assert candidate["premarket_dollar_volume_per_minute"] == candidate["expected_opening_dollar_volume_60s"]
    assert "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE" in candidate["lane_tags"]


def test_opening_burst_can_use_infq_archetype_score_for_live_gate():
    candidate = {
        "ticker": "INFQ",
        "hyper_trade_score": 3.775,
        "infq_archetype_score": 7.146,
        "opening_strategy_score": 7.146,
        "lane_tags": ["VERIFIED_CATALYST_RUNNER", "INFQ_STYLE_GOVERNMENT_SECTOR_WAVE"],
        "entry_cap": 16.6,
    }
    tape = {
        "bid": 16.2,
        "ask": 16.24,
        "quote_age_ms": 100,
        "tape_state": "DRIVE_CONFIRMING",
        "bid_collapse_flag": False,
        "opening_drive_score": 7.4,
        "volume_burst_ratio": 7.0,
        "rug_pull_score": 1.0,
        "upper_wick_fade_score": 1.0,
        "chase_risk_score": 2.0,
        "price_above_open": True,
        "premarket_high_break_confirmed": False,
        "premarket_high_reclaim_confirmed": False,
        "micro_vwap_hold": True,
        "open_execution_confidence": 7.2,
    }

    decision = evaluate_opening_burst_signal(candidate, tape, CFG, now=opening_stream_supervisor._ts("2026-05-22T13:30:45+00:00"))

    assert decision["action"] == "BUY_NOW"
    assert decision["actuals"]["raw_hyper_trade_score"] == 3.775
    assert decision["actuals"]["infq_archetype_score"] == 7.146


def test_stream_replay_truncates_prior_run_artifacts(tmp_path):
    candidate = {
        "ticker": "INFQ",
        "hyper_trade_score": 8.8,
        "lane_tags": ["VERIFIED_CATALYST_RUNNER"],
        "entry_cap": 10.7,
        "premarket_high": 10.0,
        "premarket_dollar_volume_per_minute": 100000,
    }
    first_events = [
        {"type": "quote", "symbol": "INFQ", "timestamp": "2026-05-21T13:30:06+00:00", "bid": 10.09, "ask": 10.11, "bid_size": 1200, "ask_size": 800},
        {"type": "trade", "symbol": "INFQ", "timestamp": "2026-05-21T13:30:06+00:00", "price": 10.1, "size": 30000},
    ]
    replay_opening_stream(candidate, first_events, CFG, output_dir=tmp_path)
    replay_opening_stream(candidate, first_events[:1], CFG, output_dir=tmp_path)
    assert len((tmp_path / "decisions.jsonl").read_text().splitlines()) == 1


def test_live_stream_supervisor_suppresses_duplicate_buy_proposals(tmp_path, monkeypatch):
    candidate = {"ticker": "INFQ", "hyper_trade_score": 8.8, "lane_tags": ["VERIFIED_CATALYST_RUNNER"], "entry_cap": 10.7, "premarket_high": 10.0}

    class FakeAdapter:
        def __init__(self, output_dir=None, feed=None):
            self.quote_handler = None
            self.trade_handler = None

        def subscribe_quotes_and_trades(self, symbols, quote_handler=None, trade_handler=None):
            self.quote_handler = quote_handler
            self.trade_handler = trade_handler

        def run(self):
            event = {"type": "quote", "symbol": "INFQ", "timestamp": "2026-05-21T13:30:20+00:00", "bid": 10.0, "ask": 10.01, "bid_size": 1000, "ask_size": 1000}
            self.quote_handler(event)
            self.quote_handler(event)

        def stop(self):
            pass

    monkeypatch.setattr(opening_stream_supervisor, "AlpacaStreamsAdapter", FakeAdapter)
    monkeypatch.setattr(opening_stream_supervisor, "load_live_config", lambda: {"market_data": {"feed": "sip"}})
    monkeypatch.setattr(
        opening_stream_supervisor,
        "evaluate_opening_burst_signal",
        lambda candidate, features, cfg, now: {"action": "BUY_NOW", "entry": 10.01, "limit_price": 10.01, "entry_cap": 10.7, "notional_usd": 100},
    )

    result = opening_stream_supervisor.run_live_opening_stream_supervisor([candidate], output_dir=tmp_path, cfg=CFG)
    assert result["ok"] is True
    assert len((tmp_path / "proposals.jsonl").read_text().splitlines()) == 1
    summary = json.loads((tmp_path / "final_summary.json").read_text())
    assert summary["mode"] == "shadow_no_order_submission"
    assert summary["orders_submitted"] is False
    assert summary["max_seconds"] == 900.0
    assert summary["proposal_count"] == 1
    assert summary["fast_cancel_ready"] is True
    assert summary["opening_exit_manager_ready"] is True
    proposal = json.loads((tmp_path / "proposals.jsonl").read_text().splitlines()[0])
    for key in ["first_minute_volume", "first_minute_dollar_volume", "close_in_range_pct", "spread_bps", "max_slippage_bps"]:
        assert key in proposal


def test_live_stream_supervisor_uses_total_risk_not_per_share(tmp_path, monkeypatch):
    candidate = {"ticker": "INFQ", "hyper_trade_score": 8.8, "lane_tags": ["VERIFIED_CATALYST_RUNNER"], "entry_cap": 10.7, "premarket_high": 10.0, "thesis_break": 9.5}

    class FakeAdapter:
        def __init__(self, output_dir=None, feed=None):
            self.quote_handler = None
            self.trade_handler = None

        def subscribe_quotes_and_trades(self, symbols, quote_handler=None, trade_handler=None):
            self.quote_handler = quote_handler
            self.trade_handler = trade_handler

        def run(self):
            self.quote_handler({"type": "quote", "symbol": "INFQ", "timestamp": "2026-05-21T13:30:20+00:00", "bid": 10.0, "ask": 10.01, "bid_size": 1000, "ask_size": 1000})
            self.trade_handler({"type": "trade", "symbol": "INFQ", "timestamp": "2026-05-21T13:30:21+00:00", "price": 10.0, "size": 5000})

        def stop(self):
            pass

        def snapshot(self):
            return {"market_data_connected": True, "trade_updates_connected": False, "last_error": None}

    monkeypatch.setattr(opening_stream_supervisor, "AlpacaStreamsAdapter", FakeAdapter)
    monkeypatch.setattr(opening_stream_supervisor, "load_live_config", lambda: {"market_data": {"feed": "sip"}})
    monkeypatch.setattr(
        opening_stream_supervisor,
        "evaluate_opening_burst_signal",
        lambda candidate, features, cfg, now: (
            {"action": "BUY_NOW", "entry": 10.0, "limit_price": 10.0, "entry_cap": 10.7, "notional_usd": 500}
            if float(features.get("window_volume_60s") or 0) > 0
            else {"action": "WAIT"}
        ),
    )

    result = opening_stream_supervisor.run_live_opening_stream_supervisor([candidate], output_dir=tmp_path, cfg=CFG)

    assert result["proposal_count"] == 1
    proposal = json.loads((tmp_path / "proposals.jsonl").read_text().splitlines()[0])
    assert proposal["shares"] == 50
    assert proposal["max_risk_usd"] == 25.0
    assert proposal["first_minute_volume"] == 5000.0
    assert proposal["first_minute_dollar_volume"] == 50000.0
    assert proposal["close_in_range_pct"] == 1.0
    assert proposal["spread_bps"] > 0
    assert proposal["max_slippage_bps"] == 20.0


def test_live_stream_supervisor_blocks_invalid_stop_without_masking_risk(tmp_path, monkeypatch):
    candidate = {"ticker": "INFQ", "hyper_trade_score": 8.8, "lane_tags": ["VERIFIED_CATALYST_RUNNER"], "entry_cap": 10.7, "premarket_high": 10.0, "thesis_break": 10.5}

    class FakeAdapter:
        def __init__(self, output_dir=None, feed=None):
            self.quote_handler = None

        def subscribe_quotes_and_trades(self, symbols, quote_handler=None, trade_handler=None):
            self.quote_handler = quote_handler

        def run(self):
            self.quote_handler({"type": "quote", "symbol": "INFQ", "timestamp": "2026-05-21T13:30:20+00:00", "bid": 10.0, "ask": 10.01, "bid_size": 1000, "ask_size": 1000})

        def stop(self):
            pass

        def snapshot(self):
            return {"market_data_connected": True, "trade_updates_connected": False, "last_error": None}

    monkeypatch.setattr(opening_stream_supervisor, "AlpacaStreamsAdapter", FakeAdapter)
    monkeypatch.setattr(opening_stream_supervisor, "load_live_config", lambda: {"market_data": {"feed": "sip"}})
    monkeypatch.setattr(
        opening_stream_supervisor,
        "evaluate_opening_burst_signal",
        lambda candidate, features, cfg, now: {"action": "BUY_NOW", "entry": 10.01, "limit_price": 10.01, "entry_cap": 10.7, "notional_usd": 100},
    )

    result = opening_stream_supervisor.run_live_opening_stream_supervisor([candidate], output_dir=tmp_path, cfg=CFG)

    assert result["proposal_count"] == 0
    assert result["blocked_proposal_count"] == 1
    blocked = json.loads((tmp_path / "proposals.jsonl").read_text().splitlines()[0])
    assert blocked["reason"] == "invalid_stop_not_below_entry"


def test_live_stream_supervisor_stops_after_bounded_timeout(tmp_path, monkeypatch):
    candidate = {"ticker": "INFQ", "hyper_trade_score": 8.8, "lane_tags": ["VERIFIED_CATALYST_RUNNER"], "entry_cap": 10.7, "premarket_high": 10.0}

    class FakeAdapter:
        def __init__(self, output_dir=None, feed=None):
            self.stopped = False

        def subscribe_quotes_and_trades(self, symbols, quote_handler=None, trade_handler=None):
            self.symbols = symbols

        def run(self):
            self.stop()

        def stop(self):
            self.stopped = True

        def snapshot(self):
            return {"market_data_connected": False, "trade_updates_connected": False, "last_error": None}

    monkeypatch.setattr(opening_stream_supervisor, "AlpacaStreamsAdapter", FakeAdapter)
    monkeypatch.setattr(opening_stream_supervisor, "load_live_config", lambda: {"market_data": {"feed": "sip"}})

    result = opening_stream_supervisor.run_live_opening_stream_supervisor([candidate], output_dir=tmp_path, cfg=CFG, max_seconds=0.01)

    assert result["ok"] is True
    assert result["max_seconds"] == 0.01
    assert result["orders_submitted"] is False
    assert (tmp_path / "final_summary.json").exists()
