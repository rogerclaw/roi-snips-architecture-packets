from src.adapters.federal_sources import OpenFdaAdapter, SamGovAdapter
from src.adapters.fmp_market_data import FmpMarketDataAdapter
from src.adapters.stocktwits_stream import StockTwitsStreamAdapter
from src.adapters.tradingview_screener import TradingViewScreenerAdapter


def test_fmp_movers_fail_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    res = FmpMarketDataAdapter(api_key=None).fetch_movers()
    assert res["ok"] is False
    assert res["reason"] == "missing_fmp_api_key"
    assert res["events"] == []


def test_tradingview_screener_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ROI_SNIPS_ENABLE_TRADINGVIEW_SCREENER", raising=False)
    res = TradingViewScreenerAdapter().fetch_us_movers()
    assert res["ok"] is False
    assert res["reason"] == "tradingview_screener_disabled"


def test_sam_gov_requires_api_key(monkeypatch):
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    res = SamGovAdapter(api_key=None).search_opportunities(query="INFQ")
    assert res["ok"] is False
    assert res["reason"] == "missing_sam_gov_api_key"


def test_openfda_uses_public_http_path(monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=20):
        calls.append((url, params))
        return type("Resp", (), {"ok": True, "status": 200, "data": {"results": [{"safetyreportid": "1"}]}, "error": None})()

    monkeypatch.setattr("src.adapters.federal_sources.http_get_json", fake_get)
    res = OpenFdaAdapter(api_key=None, base_url="https://api.test").search_drug_events(query="quantum", limit=1)
    assert res["ok"] is True
    assert res["count"] == 1
    assert calls[0][0] == "https://api.test/drug/event.json"
    assert calls[0][1]["search"] == "quantum"


def test_stocktwits_uses_bounded_timeout(monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=20):
        calls.append((url, params, timeout))
        return type("Resp", (), {"ok": True, "status": 200, "data": {"messages": []}, "error": None})()

    monkeypatch.setattr("src.adapters.stocktwits_stream.http_get_json", fake_get)
    res = StockTwitsStreamAdapter(base_url="https://stocktwits.test", timeout_seconds=4).fetch_symbol_stream("INFQ")
    assert res["ok"] is True
    assert calls[0][0] == "https://stocktwits.test/streams/symbol/INFQ.json"
    assert calls[0][2] == 4
