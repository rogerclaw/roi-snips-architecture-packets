from datetime import datetime, timezone

from src.research.scouts.fda_scout import FdaScout
from src.research.scouts.government_scout import GovernmentScout
from src.research.scouts.ir_scout import IRScout


class StubBenzinga:
    def __init__(self, title, created=None):
        self.title = title
        self.created = created or datetime.now(timezone.utc).isoformat()

    def fetch_events(self, page_size=100, tickers=None):
        return {
            "ok": True,
            "events": [
                {
                    "title": self.title,
                    "channels": ["news"],
                    "tickers": ["ABEO"],
                    "url": "https://example.com/item",
                    "created": self.created,
                    "updated": self.created,
                }
            ],
        }


class EmptyAlpacaNews:
    def fetch_events(self, symbols=None, limit=50):
        return {"ok": True, "events": []}


def test_ir_scout_filters_for_ir_style_updates():
    scout = IRScout(benzinga=StubBenzinga("ABEO announces partnership and conference call"), alpaca_news=EmptyAlpacaNews())
    events = scout.collect()
    assert events
    assert events[0]["source_name"] == "ir_scout"
    assert events[0]["catalyst_type"] == "product_or_partnership"


def test_fda_scout_filters_for_biotech_updates():
    scout = FdaScout(benzinga=StubBenzinga("ABEO receives FDA fast track designation"), alpaca_news=EmptyAlpacaNews())
    events = scout.collect()
    assert events
    assert events[0]["source_name"] == "fda_scout"
    assert events[0]["catalyst_type"] == "medical_or_biotech"


def test_government_scout_filters_for_contract_updates():
    scout = GovernmentScout(benzinga=StubBenzinga("ABEO wins Department of Defense contract award"), alpaca_news=EmptyAlpacaNews())
    events = scout.collect()
    assert events
    assert events[0]["source_name"] == "government_scout"
    assert events[0]["catalyst_type"] == "government_contract"


def test_government_scout_catches_chips_quantum_funding_loi():
    scout = GovernmentScout(
        benzinga=StubBenzinga("INFQ receives CHIPS Department of Commerce funding letter of intent for quantum computing"),
        alpaca_news=EmptyAlpacaNews(),
    )
    events = scout.collect()
    assert events
    assert events[0]["ticker_candidates"] == ["ABEO"]
    assert events[0]["catalyst_type"] == "government_contract"


def test_fda_scout_does_not_false_positive_on_substring_matches():
    scout = FdaScout(benzinga=StubBenzinga("Monday market roundup for semiconductor names"), alpaca_news=EmptyAlpacaNews())
    events = scout.collect()
    assert events == []


def test_keyword_scout_filters_out_stale_items():
    scout = IRScout(benzinga=StubBenzinga("ABEO announces partnership", created="2025-10-01T08:07:46+00:00"), alpaca_news=EmptyAlpacaNews())
    events = scout.collect()
    assert events == []
