from src.research.market_overlay import build_overlay_for_symbol


class StubMD:
    def get_quote(self, symbol):
        return {
            "ok": True,
            "quote": {
                "last": 10.0,
                "prev_close": 9.0,
                "bid": 9.99,
                "ask": 10.01,
                "avg20dDollarVolume": 30000000,
                "halt_status": "NONE",
            },
        }

    def get_bars_1m(self, symbol, limit=500):
        return {
            "ok": True,
            "bars": [
                {"timestamp": "2026-04-15T08:00:00-04:00", "open": 9.4, "close": 9.5, "volume": 10000},
                {"timestamp": "2026-04-15T08:01:00-04:00", "open": 9.5, "close": 9.6, "volume": 15000},
            ],
        }


def test_build_overlay_for_symbol():
    overlay = build_overlay_for_symbol(
        "AAPL",
        md=StubMD(),
        cfg={"session": {"timezone": "America/New_York"}},
    )
    assert overlay.ticker == "AAPL"
    assert overlay.tradeability_gate_pass
    assert overlay.premarket_volume == 25000
    assert overlay.gap_pct is not None
    assert overlay.execution_readiness_score > 0


class MissingDataMD:
    def get_quote(self, symbol):
        return {"ok": True, "quote": {"halt_status": "NONE"}}

    def get_bars_1m(self, symbol, limit=500):
        return {"ok": True, "bars": []}


def test_build_overlay_for_symbol_missing_data_fails_closed():
    overlay = build_overlay_for_symbol(
        "AAPL",
        md=MissingDataMD(),
        cfg={"session": {"timezone": "America/New_York"}},
    )
    assert not overlay.tradeability_gate_pass
    assert "price_missing" in overlay.tradeability_notes
    assert "average_20d_dollar_volume_missing" in overlay.tradeability_notes
    assert overlay.execution_blockers


class DailyBarsFallbackMD:
    def get_quote(self, symbol):
        return {
            "ok": True,
            "quote": {
                "last": 10.0,
                "prev_close": 9.0,
                "bid": 9.99,
                "ask": 10.01,
                "halt_status": "NONE",
            },
        }

    def get_bars_1m(self, symbol, limit=500):
        return {
            "ok": True,
            "bars": [
                {"timestamp": "2026-04-15T08:00:00-04:00", "open": 9.4, "close": 9.5, "volume": 10000},
                {"timestamp": "2026-04-15T08:01:00-04:00", "open": 9.5, "close": 9.6, "volume": 15000},
            ],
        }

    def get_bars_1d(self, symbol, limit=20):
        return {
            "ok": True,
            "bars": [{"timestamp": f"2026-04-{i:02d}T00:00:00+00:00", "close": 10.0, "volume": 3000000} for i in range(1, 21)],
        }


def test_build_overlay_for_symbol_uses_daily_bar_fallback_for_avg20():
    overlay = build_overlay_for_symbol(
        "AAPL",
        md=DailyBarsFallbackMD(),
        cfg={"session": {"timezone": "America/New_York"}},
    )
    assert overlay.average_20d_dollar_volume == 30000000.0
    assert "average_20d_dollar_volume_missing" not in overlay.execution_blockers
