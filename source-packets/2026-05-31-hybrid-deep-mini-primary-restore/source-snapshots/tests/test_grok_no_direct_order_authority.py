from src.adapters.grok_web_search import GrokWebSearchAdapter
from src.adapters.grok_x_search import GrokXSearchAdapter
from src.adapters.xai_responses import XAIResponsesAdapter
from src.workflows.grok_research_pipeline import run_grok_research_pipeline


def test_grok_adapters_have_no_order_authority_methods():
    forbidden = {
        "place_order",
        "preview_order",
        "submit_order",
        "replace_order",
        "cancel_order",
        "list_open_orders",
        "get_account",
        "get_positions",
    }
    for obj in [XAIResponsesAdapter(client=object()), GrokXSearchAdapter(), GrokWebSearchAdapter()]:
        assert forbidden.isdisjoint(set(dir(obj)))


class FakeX:
    def __init__(self):
        self.queries = []

    def run_queries(self, queries, limit=8):
        self.queries = list(queries)
        return [{"ok": False, "reason": "offline"}]


class FakeWeb:
    def search_web(self, query, limit=8):
        return {"ok": False, "reason": "offline"}


def test_grok_pipeline_fail_closed_no_order_surface(tmp_path, monkeypatch):
    monkeypatch.setattr("src.workflows.grok_research_pipeline.repo_root", lambda: tmp_path)
    result = run_grok_research_pipeline(trading_date="2026-05-30", seed_packet={"fresh_news": [{"ticker": "ABCD"}]}, x_adapter=FakeX(), web_adapter=FakeWeb())

    assert result["status"] == "COMPLETED_RESEARCH_ONLY"
    assert not (tmp_path / "runs" / "2026-05-30" / "trade_authorization_ticket.json").exists()
    summary = (tmp_path / "runs" / "2026-05-30" / "grok" / "ticket_input_summary.json").read_text()
    assert "place_order" not in summary
    assert "preview_order" not in summary


def test_grok_pipeline_uses_scheduled_discovery_artifacts_as_seed(tmp_path, monkeypatch):
    monkeypatch.setattr("src.workflows.grok_research_pipeline.repo_root", lambda: tmp_path)
    run_root = tmp_path / "runs" / "2026-06-01"
    (run_root / "normalized").mkdir(parents=True)
    (run_root / "raw").mkdir(parents=True)
    (run_root / "normalized" / "discovered_symbols.json").write_text('["ABCD", "WXYZ"]')
    (run_root / "raw" / "top_raw_candidates.json").write_text('[{"ticker":"MRAM","source_name":"benzinga"}]')
    fake_x = FakeX()

    result = run_grok_research_pipeline(trading_date="2026-06-01", x_adapter=fake_x, web_adapter=FakeWeb())

    assert result["status"] == "COMPLETED_RESEARCH_ONLY"
    seed = (run_root / "research_seed_packet.json").read_text()
    assert '"candidate_count": 3' in seed
    assert "$ABCD stock premarket why up catalyst" in fake_x.queries
    assert "$MRAM stock premarket why up catalyst" in fake_x.queries
