from src.research.scouts.exchange_scout import ExchangeScout


class StubBenzinga:
    def fetch_events(self, page_size=100, tickers=None):
        return {
            "ok": True,
            "events": [
                {
                    "title": "MRAM surges after contract award",
                    "channels": ["market_news"],
                    "tickers": ["MRAM"],
                    "url": "https://example.com/mram",
                    "created": "2026-04-30T11:00:00+00:00",
                    "updated": "2026-04-30T11:05:00+00:00",
                }
            ],
        }


class StubAlpacaNews:
    def fetch_events(self, symbols=None, limit=50):
        return {
            "ok": True,
            "events": [
                {
                    "headline": "MRAM wins new defense deal",
                    "summary": "Contract expands revenue visibility.",
                    "source": "alpaca",
                    "symbols": ["MRAM"],
                    "url": "https://example.com/alpaca-mram",
                    "created_at": "2026-04-30T11:01:00+00:00",
                    "updated_at": "2026-04-30T11:06:00+00:00",
                }
            ],
        }


class StubMD:
    def get_quote(self, symbol):
        return {
            "ok": True,
            "quote": {
                "last": 11.0,
                "prev_close": 10.0,
                "bid": 10.98,
                "ask": 11.02,
                "avg20dDollarVolume": 18000000,
                "halt_status": "NONE",
            },
        }

    def get_bars_1m(self, symbol, limit=500):
        return {
            "ok": True,
            "bars": [
                {"timestamp": "2026-04-30T08:00:00-04:00", "open": 10.4, "close": 10.7, "volume": 30000},
                {"timestamp": "2026-04-30T08:01:00-04:00", "open": 10.7, "close": 11.0, "volume": 40000},
            ],
        }


def test_exchange_scout_combines_news_and_market_confirmation():
    scout = ExchangeScout(benzinga=StubBenzinga(), alpaca_news=StubAlpacaNews(), md=StubMD())
    events = scout.collect()
    assert events
    first = events[0]
    assert first["source_name"] == "exchange_scout"
    assert first["ticker_candidates"] == ["MRAM"]
    assert any("premarket_dollar_volume=" in note for note in first["notes"])
    assert first["structured_flag"] is True


def test_exchange_scout_requested_mode_only_emits_requested_symbols():
    scout = ExchangeScout(benzinga=StubBenzinga(), alpaca_news=StubAlpacaNews(), md=StubMD())
    events = scout.collect(["MRAM"])
    assert events
    assert all(event["ticker_candidates"] == ["MRAM"] for event in events)
