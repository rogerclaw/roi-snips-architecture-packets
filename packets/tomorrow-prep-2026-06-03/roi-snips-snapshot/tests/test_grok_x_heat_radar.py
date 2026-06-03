from src.research.grok_x_heat_radar import run_grok_x_heat_radar


class FakeXAdapter:
    def run_queries(self, queries, limit=8):
        assert queries
        return [
            {
                "ok": True,
                "model": "grok-4.3",
                "content": "$ABCD premarket runner on FDA catalyst. $ABCD volume building.",
                "citations": ["https://x.com/trader/status/1"],
            }
        ]


def test_grok_x_heat_radar_outputs_candidates_with_threads():
    result = run_grok_x_heat_radar(
        {"fresh_news": [{"ticker": "ABCD"}], "trading_date": "2026-05-30"},
        adapter=FakeXAdapter(),
    )

    assert result["status"] == "completed"
    assert result["x_candidate_count"] == 1
    assert result["candidates"][0]["ticker"] == "ABCD"
    assert result["candidates"][0]["key_threads"] == ["https://x.com/trader/status/1"]
    assert result["candidates"][0]["needs_verification"] is True
