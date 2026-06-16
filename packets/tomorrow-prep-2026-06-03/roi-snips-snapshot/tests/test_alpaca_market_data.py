from src.adapters.alpaca_market_data import AlpacaMarketDataAdapter


class FallbackQuoteAdapter(AlpacaMarketDataAdapter):
    def __init__(self):
        self.feed = "sip"
        self.allow_iex_fallback = True
        self.calls = []

    def _quote_for_feed(self, symbol: str, feed_name: str):
        self.calls.append((symbol, feed_name))
        if feed_name == "sip":
            return {
                "ok": False,
                "reason": 'alpaca_quote_unavailable:{"message":"subscription does not permit querying recent SIP data"}',
                "feed": "sip",
            }
        return {
            "ok": True,
            "quote": {"bid": 10.0, "ask": 10.02, "last": 10.01},
            "feed": "iex",
        }


def test_alpaca_quote_falls_back_to_iex_when_sip_recent_quote_entitlement_missing():
    adapter = FallbackQuoteAdapter()
    result = adapter.get_quote("SPY")
    assert result["ok"]
    assert result["feed"] == "iex"
    assert result["requested_feed"] == "sip"
    assert result["fallback_from_feed"] == "sip"
    assert result["quote"]["data_scope_note"]
    assert adapter.calls == [("SPY", "sip"), ("SPY", "iex")]


def test_alpaca_quote_does_not_fallback_for_non_sip_error():
    adapter = FallbackQuoteAdapter()

    def fail_for_feed(symbol: str, feed_name: str):
        adapter.calls.append((symbol, feed_name))
        return {"ok": False, "reason": "alpaca_quote_unavailable:network_down", "feed": feed_name}

    adapter._quote_for_feed = fail_for_feed
    result = adapter.get_quote("SPY")
    assert not result["ok"]
    assert result["feed"] == "sip"
    assert adapter.calls == [("SPY", "sip")]
