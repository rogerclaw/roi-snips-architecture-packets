import json

from src.workflows.continuation_replay import replay_captured_continuation


def test_captured_tape_replay_writes_summary_without_order_submission(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "raw_quotes.jsonl").write_text(json.dumps({"symbol": "INFQ", "type": "quote", "timestamp": "2026-05-27T13:30:10+00:00", "bid": 12.0, "ask": 12.02}) + "\n")
    (source / "raw_trades.jsonl").write_text(json.dumps({"symbol": "INFQ", "type": "trade", "timestamp": "2026-05-27T13:30:11+00:00", "price": 12.01, "size": 100}) + "\n")

    summary = replay_captured_continuation(source_run_dir=source, candidate={"ticker": "INFQ", "entry_cap": 12.5}, output_dir=tmp_path / "out")

    assert summary["target_symbol"] == "INFQ"
    assert summary["raw_quote_count"] == 1
    assert summary["raw_trade_count"] == 1
    assert summary["proposal_count"] in {0, 1}
    assert (tmp_path / "out" / "continuation_replay_summary.json").exists()
