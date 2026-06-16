import json
import subprocess

from src.adapters.grok_search import GrokSearchAdapter


def test_grok_search_invokes_openclaw_web_search(monkeypatch):
    seen = {}

    def fake_run(command, capture_output=True, text=True, timeout=45, check=False):
        seen["command"] = command
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "outputs": [
                        {
                            "result": {
                                "provider": "grok",
                                "model": "grok-4.3",
                                "query": "site:x.com $MRAM stock",
                                "content": "$MRAM is getting attention on X",
                                "citations": ["https://x.com/search?q=%24MRAM"],
                            }
                        }
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.adapters.grok_search.subprocess.run", fake_run)

    res = GrokSearchAdapter(openclaw_bin="openclaw", timeout_seconds=45).search("site:x.com $MRAM stock", limit=3)

    assert res["ok"]
    assert res["model"] == "grok-4.3"
    assert res["citations"] == ["https://x.com/search?q=%24MRAM"]
    assert seen["command"] == [
        "openclaw",
        "infer",
        "web",
        "search",
        "--provider",
        "grok",
        "--query",
        "site:x.com $MRAM stock",
        "--limit",
        "3",
        "--json",
    ]


def test_grok_fetch_x_candidates_extracts_mentions_and_citations(monkeypatch):
    def fake_search(self, query, *, limit=5):
        return {
            "ok": True,
            "provider": "grok",
            "model": "grok-4.3",
            "query": query,
            "content": "$MRAM chatter is accelerating. $MRAM contract posts are circulating. $ABEO FDA chatter appears.",
            "citations": ["https://x.com/example/status/1", "https://finance.yahoo.com/quote/MRAM"],
        }

    monkeypatch.setattr("src.adapters.grok_search.GrokSearchAdapter.search", fake_search)

    res = GrokSearchAdapter().fetch_x_candidates(tickers=["MRAM", "ABEO"])

    assert res["ok"]
    assert res["auth_mode"] == "openclaw_grok_web_search"
    assert res["candidates"][0]["ticker"] == "MRAM"
    assert res["candidates"][0]["mentions"] == 2
    assert res["candidates"][0]["evidence_urls"] == ["https://x.com/example/status/1"]
