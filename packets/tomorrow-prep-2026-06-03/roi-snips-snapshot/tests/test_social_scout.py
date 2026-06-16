from src.research.scouts.social_scout import SocialScout


class EmptyReddit:
    def fetch_themes(self):
        return {"ok": True, "trending": []}


class EmptyX:
    def fetch_recent(self, query, max_results=25):
        return {"ok": False, "reason": "missing_x_bearer_token", "optional": True}


class StubGrok:
    def fetch_x_candidates(self, tickers=None):
        assert tickers == ["MRAM"]
        return {
            "ok": True,
            "candidates": [
                {
                    "ticker": "MRAM",
                    "mentions": 3,
                    "evidence_urls": ["https://x.com/example/status/1"],
                    "snippets": ["$MRAM attention is accelerating around a fresh contract catalyst."],
                }
            ],
        }


def test_social_scout_adds_grok_x_social_events():
    events = SocialScout(reddit=EmptyReddit(), x_adapter=EmptyX(), grok=StubGrok()).collect(tickers=["MRAM"])

    grok_events = [event for event in events if event["source_name"] == "grok_x_search"]
    assert len(grok_events) == 1
    event = grok_events[0]
    assert event["ticker_candidates"] == ["MRAM"]
    assert event["social_flag"] is True
    assert event["official_flag"] is False
    assert event["structured_flag"] is False
    assert event["source_url"] == "https://x.com/example/status/1"
    assert "source=grok_x_search" in event["notes"]
    assert "citation=https://x.com/example/status/1" in event["notes"]
