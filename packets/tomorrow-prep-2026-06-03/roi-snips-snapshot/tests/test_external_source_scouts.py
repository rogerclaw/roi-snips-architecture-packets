from src.research.scouts.external_source_scouts import ExternalMoversScout, FederalCatalystScout


class MissingFmp:
    def fetch_movers(self):
        return {"ok": False, "reason": "missing_fmp_api_key", "events": []}


class DisabledTradingView:
    def fetch_us_movers(self):
        return {"ok": False, "reason": "tradingview_screener_disabled", "rows": []}


class EmptyStockTwits:
    def fetch_symbol_stream(self, symbol, limit=20):
        return {"ok": False, "reason": "stocktwits_http_error", "messages": []}


class FmpWithInfq:
    def fetch_movers(self):
        return {"ok": True, "events": [{"symbol": "INFQ", "name": "Infleqtion", "change_percent": 39.8, "volume": 6_000_000}]}


class StockTwitsWithInfq:
    def fetch_symbol_stream(self, symbol, limit=20):
        return {
            "ok": True,
            "messages": [
                {"body": "$INFQ squeeze", "sentiment": "Bullish"},
                {"body": "$INFQ CHIPS", "sentiment": "Bullish"},
            ],
        }


def test_external_movers_degrades_without_credentials_but_does_not_fake_events():
    scout = ExternalMoversScout(fmp=MissingFmp(), stocktwits=EmptyStockTwits(), tradingview=DisabledTradingView())
    assert scout.collect() == []


def test_external_movers_emits_structured_mover_when_source_present():
    scout = ExternalMoversScout(fmp=FmpWithInfq(), stocktwits=StockTwitsWithInfq(), tradingview=DisabledTradingView())
    events = scout.collect()
    assert len(events) == 1
    event = events[0]
    assert event["ticker_candidates"] == ["INFQ"]
    assert event["source_name"] == "external_movers_scout"
    assert event["structured_flag"] is True
    assert event["social_flag"] is True
    assert any("stocktwits_messages=2" == note for note in event["notes"])


def test_external_movers_bounds_stocktwits_enrichment():
    class ManyFmp:
        def fetch_movers(self):
            return {"ok": True, "events": [{"symbol": "INFQ"}, {"symbol": "MRAM"}]}

    class CountingStockTwits:
        def __init__(self):
            self.calls = []

        def fetch_symbol_stream(self, symbol, limit=20):
            self.calls.append(symbol)
            return {"ok": True, "messages": []}

    stocktwits = CountingStockTwits()
    scout = ExternalMoversScout(fmp=ManyFmp(), stocktwits=stocktwits, tradingview=DisabledTradingView(), max_stocktwits_enrichment=1)
    events = scout.collect()
    assert len(events) == 2
    assert stocktwits.calls == ["INFQ"]
    assert any("degraded=MRAM:stocktwits_enrichment_budget_exhausted" == note for note in events[1]["notes"])


def test_federal_catalyst_scout_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ROI_SNIPS_ENABLE_FEDERAL_CATALYST_SCOUT", raising=False)
    scout = FederalCatalystScout()
    assert scout.collect(["INFQ"]) == []


class EmptySam:
    def search_opportunities(self, query, limit=10):
        return {"ok": False, "reason": "missing_sam_gov_api_key", "opportunities": []}


class UsaWithInfq:
    def search_awards(self, query, limit=10):
        return {"ok": True, "awards": [{"Recipient Name": "INFQ"}]}


class EmptyClinical:
    def search_studies(self, query, limit=10):
        return {"ok": True, "studies": []}


class EmptyFda:
    def search_drug_events(self, query, limit=10):
        return {"ok": True, "events": []}


def test_federal_catalyst_scout_emits_official_structured_evidence():
    scout = FederalCatalystScout(sam=EmptySam(), usaspending=UsaWithInfq(), clinical=EmptyClinical(), openfda=EmptyFda())
    events = scout.collect(["INFQ"])
    assert len(events) == 1
    event = events[0]
    assert event["ticker_candidates"] == ["INFQ"]
    assert event["catalyst_type"] == "government_contract"
    assert event["official_flag"] is True
    assert event["structured_flag"] is True
    assert any("sam_degraded=missing_sam_gov_api_key" == note for note in event["notes"])
