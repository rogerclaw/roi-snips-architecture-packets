from src.workflows.grok_d_research_bridge import (
    GROK_REQUIRED_BLOCKER,
    grok_required_for_live_research,
    run_governed_grok_d_research,
)
from tests.runbook_helpers import ranked_row


class FakeGrokAdapter:
    def __init__(self, result):
        self.result = result
        self.queries = []

    def search(self, query, *, limit=10):
        self.queries.append((query, limit))
        return self.result


def test_grok_d_research_is_primary_live_required_mode():
    assert grok_required_for_live_research({"mode": "grok_d_research", "require_for_live_research": True}) is True
    assert grok_required_for_live_research({"require_grok_for_live_research": True}) is True


def test_grok_d_research_can_create_one_research_ticket_packet(tmp_path):
    adapter = FakeGrokAdapter(
        {
            "ok": True,
            "provider": "grok",
            "model": "grok-4.3",
            "content": "$ABCD fresh contract catalyst is accelerating on X with structured news confirmation.",
            "citations": ["https://x.com/search?q=%24ABCD", "https://example.com/news/abcd"],
        }
    )

    result = run_governed_grok_d_research([ranked_row("ABCD")], {"generated_at_utc": "2026-05-30T13:00:00+00:00"}, tmp_path, adapter=adapter)

    assert result.success is True
    packet = result.structured_packet
    assert packet["source_mode"] == "governed_grok_d_research"
    assert packet["best_pick"] == "ABCD"
    assert packet["trade_authorization"]["authorized"] is True
    assert packet["trade_authorization"]["backup_execution_allowed"] is False
    assert packet["deterministic_fallback_executable_allowed"] is False


def test_grok_social_only_hype_cannot_authorize(tmp_path):
    row = ranked_row("ABCD")
    row["cluster"]["official_sources"] = []
    row["cluster"]["structured_sources"] = []
    row["research_scorecard"]["official_confirmation_count"] = 0
    row["research_scorecard"]["structured_confirmation_count"] = 0

    result = run_governed_grok_d_research(
        [row],
        {"generated_at_utc": "2026-05-30T13:00:00+00:00"},
        tmp_path,
        adapter=FakeGrokAdapter({"ok": True, "provider": "grok", "model": "grok-4.3", "content": "$ABCD moon", "citations": ["https://x.com/a"]}),
    )

    assert result.success is True
    assert result.structured_packet["trade_authorization"]["authorized"] is False
    assert "grok_social_only_not_authorizing" in result.structured_packet["trade_authorization"]["blockers"]


def test_grok_failure_is_no_trade_not_fallback(tmp_path):
    result = run_governed_grok_d_research(
        [ranked_row("ABCD")],
        {},
        tmp_path,
        adapter=FakeGrokAdapter({"ok": False, "reason": GROK_REQUIRED_BLOCKER}),
    )

    assert result.success is False
    assert result.structured_packet is None
    assert result.error == GROK_REQUIRED_BLOCKER
