from src.common.provider_factory import (
    build_live_readiness_report,
    build_market_data_adapter,
    build_trade_adapter,
    configured_broker_provider,
    configured_market_data_provider,
)


def test_configured_providers_read_from_cfg():
    cfg = {"broker": {"provider": "webull"}, "market_data": {"provider": "alpaca"}}
    assert configured_broker_provider(cfg) == "webull"
    assert configured_market_data_provider(cfg) == "alpaca"


def test_build_market_data_adapter_webull():
    adapter = build_market_data_adapter({"market_data": {"provider": "webull"}})
    assert adapter.__class__.__name__ == "WebullMarketDataAdapter"


def test_build_trade_adapter_webull():
    adapter = build_trade_adapter({"broker": {"provider": "webull"}})
    assert adapter.__class__.__name__ == "WebullTradeAdapter"


def test_webull_trade_adapter_exposes_account_state(monkeypatch):
    from src.adapters import webull_trade

    class StubRest:
        def account_balance(self, account_id):
            assert account_id == "acct_1"

            class Response:
                ok = True
                data = {"total_cash_balance": "950.00", "available_buying_power": "950.00"}

            return Response()

    monkeypatch.setattr(webull_trade, "WebullRESTClient", StubRest)
    adapter = webull_trade.WebullTradeAdapter(
        webull_trade.WebullTradeConfig(app_key="key", app_secret="secret", account_id="acct_1")
    )

    account = adapter.get_account()

    assert account["ok"]
    assert account["account"]["cash"] == "950.00"
    assert account["account"]["buying_power"] == "950.00"


def test_live_readiness_report_flags_missing_bid_ask(monkeypatch):
    class StubMD:
        def healthcheck(self, symbol="SPY"):
            return {
                "ok": True,
                "quote": {"quote": {"last": 10.0, "prev_close": 9.5, "bid": None, "ask": None}, "feed": "sip"},
                "bars": {"ok": True},
                "feed": "sip",
            }

    class StubTrade:
        def healthcheck(self):
            return {"ok": True}

    monkeypatch.setattr("src.common.provider_factory.build_market_data_adapter", lambda cfg=None, provider=None: StubMD())
    monkeypatch.setattr("src.common.provider_factory.build_trade_adapter", lambda cfg=None, provider=None: StubTrade())
    monkeypatch.setattr("src.common.provider_factory.active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "in_entry_window": True, "force_flat": False})
    monkeypatch.setattr("src.common.provider_factory.session_phase", lambda cfg: "ENTRY_WINDOW")

    report = build_live_readiness_report(
        {
            "broker": {"provider": "alpaca"},
            "market_data": {"provider": "alpaca", "require_bid_ask": True, "required_feed_for_full_mode": "sip"},
        }
    )
    assert not report["ok"]
    assert report["session_phase"] == "ENTRY_WINDOW"
    assert "bid_ask_missing_for_execution" in report["execution_blockers"]


def test_live_readiness_report_flags_sip_entitlement_and_broker_drift(monkeypatch):
    class StubMD:
        def healthcheck(self, symbol="SPY"):
            return {
                "ok": False,
                "quote": {"ok": False, "reason": 'alpaca_quote_unavailable:{"message":"subscription does not permit querying recent SIP data"}'},
                "bars": {"ok": True, "bars": []},
                "feed": "sip",
            }

        def runtime_environment(self):
            return {"provider": "alpaca_market_data", "feed": "sip"}

    class StubTrade:
        def healthcheck(self):
            return {"ok": True}

        def runtime_environment(self):
            return {"provider": "alpaca", "environment": "paper", "base_url": "https://paper-api.alpaca.markets"}

    monkeypatch.setattr("src.common.provider_factory.build_market_data_adapter", lambda cfg=None, provider=None: StubMD())
    monkeypatch.setattr("src.common.provider_factory.build_trade_adapter", lambda cfg=None, provider=None: StubTrade())
    monkeypatch.setattr("src.common.provider_factory.active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "in_entry_window": True, "force_flat": False})
    monkeypatch.setattr("src.common.provider_factory.session_phase", lambda cfg: "ENTRY_WINDOW")

    report = build_live_readiness_report(
        {
            "broker": {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"},
            "market_data": {"provider": "alpaca", "require_bid_ask": False, "require_prior_close": False, "required_feed_for_full_mode": "sip"},
        }
    )
    assert "market_data_entitlement_missing:sip_recent_quotes" in report["execution_blockers"]
    assert "broker_environment_mismatch:live!=paper" in report["execution_blockers"]
    assert "broker_base_url_mismatch" in report["execution_blockers"]


def test_live_readiness_accepts_complete_quote(monkeypatch):
    class StubMD:
        def healthcheck(self, symbol="SPY"):
            return {
                "ok": True,
                "quote": {
                    "ok": True,
                    "feed": "iex",
                    "quote": {
                        "bid": 100.0,
                        "ask": 100.05,
                        "last": 100.02,
                        "prev_close": 99.5,
                    },
                },
                "bars": {"ok": True, "bars": []},
                "feed": "iex",
            }

        def runtime_environment(self):
            return {"provider": "alpaca_market_data", "feed": "iex"}

    class StubTrade:
        def healthcheck(self):
            return {"ok": True}

        def runtime_environment(self):
            return {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"}

    monkeypatch.setattr("src.common.provider_factory.build_market_data_adapter", lambda cfg=None, provider=None: StubMD())
    monkeypatch.setattr("src.common.provider_factory.build_trade_adapter", lambda cfg=None, provider=None: StubTrade())
    monkeypatch.setattr("src.common.provider_factory.active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "in_entry_window": True, "force_flat": False})
    monkeypatch.setattr("src.common.provider_factory.session_phase", lambda cfg: "ENTRY_WINDOW")
    monkeypatch.delenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", raising=False)
    monkeypatch.delenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", raising=False)

    report = build_live_readiness_report(
        {
            "broker": {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"},
            "market_data": {"provider": "alpaca", "require_bid_ask": True, "require_prior_close": True, "required_feed_for_full_mode": "iex"},
        }
    )
    assert report["ok"]
    assert report["execution_blockers"] == []


def test_live_readiness_can_skip_broker_state_for_audit(monkeypatch):
    class StubMD:
        def healthcheck(self, symbol="SPY"):
            return {
                "ok": True,
                "quote": {
                    "ok": True,
                    "feed": "sip",
                    "quote": {"bid": 100.0, "ask": 100.05, "last": 100.02, "prev_close": 99.5},
                },
                "bars": {"ok": True, "bars": []},
                "feed": "sip",
            }

    class StubTrade:
        healthcheck_calls = 0
        position_calls = 0

        def healthcheck(self):
            self.healthcheck_calls += 1
            return {"ok": True}

        def list_positions(self):
            self.position_calls += 1
            return {"ok": True, "positions": [{"symbol": "SPY", "qty": 1}]}

        def runtime_environment(self):
            return {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"}

    trade = StubTrade()
    monkeypatch.setattr("src.common.provider_factory.build_market_data_adapter", lambda cfg=None, provider=None: StubMD())
    monkeypatch.setattr("src.common.provider_factory.build_trade_adapter", lambda cfg=None, provider=None: trade)
    monkeypatch.setattr("src.common.provider_factory.active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "in_entry_window": True, "force_flat": False})
    monkeypatch.setattr("src.common.provider_factory.session_phase", lambda cfg: "ENTRY_WINDOW")

    report = build_live_readiness_report(
        {
            "broker": {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"},
            "market_data": {"provider": "alpaca", "require_bid_ask": True, "require_prior_close": True, "required_feed_for_full_mode": "sip"},
        },
        inspect_broker_state=False,
    )
    assert trade.healthcheck_calls == 0
    assert trade.position_calls == 0
    assert not report["ok"]
    assert report["broker_health"]["reason"] == "broker_state_inspection_skipped"
    assert report["position_state"]["positions"] == []
    assert "broker_state_inspection_skipped" in report["execution_blockers"]


def test_live_readiness_requires_live_armed_when_configured(monkeypatch):
    class StubMD:
        def healthcheck(self, symbol="SPY"):
            return {
                "ok": True,
                "quote": {
                    "ok": True,
                    "feed": "sip",
                    "quote": {"bid": 100.0, "ask": 100.05, "last": 100.02, "prev_close": 99.5},
                },
                "bars": {"ok": True, "bars": []},
                "feed": "sip",
            }

    class StubTrade:
        def healthcheck(self):
            return {"ok": True}

        def runtime_environment(self):
            return {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"}

    monkeypatch.setattr("src.common.provider_factory.build_market_data_adapter", lambda cfg=None, provider=None: StubMD())
    monkeypatch.setattr("src.common.provider_factory.build_trade_adapter", lambda cfg=None, provider=None: StubTrade())
    monkeypatch.setattr("src.common.provider_factory.active_guards", lambda cfg: {"live_armed": False, "kill_switch": False, "disable_entries": False, "in_entry_window": True, "force_flat": False})
    monkeypatch.setattr("src.common.provider_factory.session_phase", lambda cfg: "ENTRY_WINDOW")

    report = build_live_readiness_report(
        {
            "controls": {"require_live_armed_for_entries": True},
            "broker": {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"},
            "market_data": {"provider": "alpaca", "require_bid_ask": True, "require_prior_close": True, "required_feed_for_full_mode": "sip"},
        }
    )
    assert not report["ok"]
    assert "live_armed_missing" in report["execution_blockers"]


def test_live_readiness_blocks_iex_fallback_when_full_mode_requires_sip(monkeypatch):
    class StubMD:
        def healthcheck(self, symbol="SPY"):
            return {
                "ok": True,
                "quote": {
                    "ok": True,
                    "feed": "iex",
                    "requested_feed": "sip",
                    "fallback_from_feed": "sip",
                    "quote": {
                        "bid": 100.0,
                        "ask": 100.05,
                        "last": 100.02,
                        "prev_close": 99.5,
                    },
                },
                "bars": {"ok": True, "bars": []},
                "feed": "iex",
                "requested_feed": "sip",
            }

        def runtime_environment(self):
            return {"provider": "alpaca_market_data", "feed": "sip", "allow_iex_fallback": True}

    class StubTrade:
        def healthcheck(self):
            return {"ok": True}

        def runtime_environment(self):
            return {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"}

    monkeypatch.setattr("src.common.provider_factory.build_market_data_adapter", lambda cfg=None, provider=None: StubMD())
    monkeypatch.setattr("src.common.provider_factory.build_trade_adapter", lambda cfg=None, provider=None: StubTrade())
    monkeypatch.setattr("src.common.provider_factory.active_guards", lambda cfg: {"live_armed": True, "kill_switch": False, "disable_entries": False, "in_entry_window": True, "force_flat": False})
    monkeypatch.setattr("src.common.provider_factory.session_phase", lambda cfg: "ENTRY_WINDOW")
    monkeypatch.delenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", raising=False)
    monkeypatch.delenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", raising=False)

    report = build_live_readiness_report(
        {
            "broker": {"provider": "alpaca", "environment": "live", "base_url": "https://api.alpaca.markets"},
            "market_data": {"provider": "alpaca", "require_bid_ask": True, "require_prior_close": True, "required_feed_for_full_mode": "sip"},
        }
    )
    assert not report["ok"]
    assert "feed_requirement_mismatch:sip!=iex" in report["execution_blockers"]
    assert "bid_ask_missing_for_execution" not in report["execution_blockers"]
    assert "last_price_missing_for_execution" not in report["execution_blockers"]
