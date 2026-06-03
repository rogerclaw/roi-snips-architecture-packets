from src.adapters.grok_search import GrokSearchAdapter
from src.research.social_velocity import grok_x_narrative_from_events


def test_grok_x_adapter_is_optional_and_extracts_ticker_narratives(monkeypatch) -> None:
    class Completed:
        returncode = 0
        stdout = '{"ok": true, "outputs": [{"result": {"provider": "grok", "query": "q", "content": "$INFQ gaining on contract chatter", "citations": ["https://x.com/a/status/1"]}}]}'
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Completed())
    result = GrokSearchAdapter(enabled=True).fetch_x_candidates(["INFQ"])

    assert result["auth_mode"] == "openclaw_grok_web_search"
    assert result["candidates"][0]["ticker"] == "INFQ"
    assert result["candidates"][0]["evidence_urls"] == ["https://x.com/a/status/1"]

    assert GrokSearchAdapter(enabled=False).search("anything")["optional"] is True


def test_grok_only_candidate_is_social_only_not_validated():
    row = grok_x_narrative_from_events(
        "INFQ",
        [{"ticker_candidates": ["INFQ"], "source_name": "grok_x", "social_flag": True, "headline": "INFQ moon", "source_url": "https://x.com/a"}],
    )

    assert row["ticker"] == "INFQ"
    assert row["rumor_vs_catalyst_flag"] == "social_only"
    assert row["pump_language_score"] > 0
    assert row["key_threads"] == ["https://x.com/a"]


def test_grok_with_structured_event_is_corroborated_but_not_self_validating():
    row = grok_x_narrative_from_events(
        "INFQ",
        [
            {"ticker_candidates": ["INFQ"], "source_name": "grok_x", "social_flag": True, "headline": "INFQ chatter"},
            {"ticker_candidates": ["INFQ"], "source_name": "benzinga", "structured_flag": True, "headline": "INFQ official coverage"},
        ],
    )

    assert row["rumor_vs_catalyst_flag"] == "corroborated_or_none"
