import json

from src.workflows.deep_mini_bridge import build_deep_mini_brief, build_fallback_best_pick_packet, parse_deep_mini_output, run_governed_deep_mini, write_deep_mini_input


def test_build_deep_mini_brief_mentions_shortlist():
    brief = build_deep_mini_brief(
        [{"ticker": "MRAM", "cluster": {"primary_ticker": "MRAM", "claim_summary": "MRAM wins contract"}, "research_scorecard": {"notes": ["official_confirmations=1"]}}],
        {"foo": "bar", "execution_eligible": [{"ticker": "MRAM"}]},
    )
    assert "MRAM" in brief
    assert "single best" in brief.lower()
    assert "Known context:" in brief
    assert "Sub-questions to answer:" in brief
    assert "Out of scope:" in brief
    assert "execution_eligible_tickers" in brief
    assert '"execution_eligible":' not in brief


def test_parse_deep_mini_output_extracts_best_pick_and_backups():
    output = """
# Executive summary
MRAM has the strongest fresh contract catalyst.

# Best pick: MRAM – Everspin
- Catalyst: contract award
- Entry: above 10.50

# Ranked backups
1. ABEO - biotech follow-through
2. OPTT - government contract chatter

# Why the best pick won over the others
It has the cleanest evidence stack.

# Key invalidation risks / what would make this a no-trade instead
- loses VWAP quickly
- volume fades after the open
"""
    packet = parse_deep_mini_output(output, [{"ticker": "MRAM"}], {"generated_at_utc": "2026-04-30T15:00:00Z"})
    assert packet.best_pick == "MRAM"
    assert packet.ranked_backups[0]["ticker"] == "ABEO"
    assert "cleanest evidence" in (packet.why_best_pick_wins or "")
    assert "loses VWAP quickly" in packet.key_invalidation_risks
    assert packet.suggested_buy_zone == "above 10.50"


def test_parse_deep_mini_output_rejects_out_of_shortlist_best_pick():
    output = """
# Executive summary
XYZ looks good.

# Best pick: XYZ
- Catalyst: outside shortlist
"""
    packet = parse_deep_mini_output(output, [{"ticker": "MRAM"}], {"generated_at_utc": "2026-04-30T15:00:00Z"})
    assert packet.best_pick is None
    assert any("out_of_shortlist" in caveat for caveat in packet.caveats)


def test_parse_deep_mini_output_reads_strict_json_pick():
    output = json.dumps(
        {
            "ticker": "ABEO",
            "exact_catalyst": "fresh FDA catalyst",
            "suggested_buy_zone": "wait for VWAP reclaim",
            "same_day_upside_target": "12.50",
            "one_to_three_day_upside_target": "15.00",
            "thesis_break_level": "9.80",
            "profit_taking_triggers": ["vertical spike into target"],
            "danger_signals": ["VWAP loss"],
        }
    )
    packet = parse_deep_mini_output(output, [{"ticker": "MRAM"}, {"ticker": "ABEO"}], {"generated_at_utc": "2026-04-30T15:00:00Z"})
    assert packet.best_pick == "ABEO"
    assert packet.best_pick_summary == "fresh FDA catalyst"
    assert packet.suggested_buy_zone == "wait for VWAP reclaim"
    assert packet.profit_taking_triggers == ["vertical spike into target"]


def test_parse_deep_mini_output_flags_incomplete_strict_json():
    output = json.dumps({"ticker": "ABEO", "exact_catalyst": "fresh FDA catalyst"})
    packet = parse_deep_mini_output(output, [{"ticker": "ABEO"}], {"generated_at_utc": "2026-04-30T15:00:00Z"})
    assert packet.best_pick == "ABEO"
    assert any(str(caveat).startswith("deep_mini_json_missing_required_fields:") for caveat in packet.caveats)


def test_run_governed_deep_mini_writes_summary_output_and_packet(tmp_path, monkeypatch):
    runner = tmp_path / "deep-research-runner"
    runner.write_text("#!/bin/sh\n")

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, cwd, capture_output, text, timeout, check):
        summary_path = command[command.index("--summary-json") + 1]
        with open(summary_path, "w") as f:
            json.dump(
                {
                    "success": True,
                    "route_chosen": "deep_mini",
                    "executor_output": "# Executive summary\nMRAM stands out.\n\n# Best pick: MRAM\n- Catalyst: contract award\n\n# Ranked backups\n1. ABEO - biotech\n",
                },
                f,
            )
        return Completed()

    monkeypatch.setattr("src.workflows.deep_mini_bridge.subprocess.run", fake_run)
    result = run_governed_deep_mini(
        [{"ticker": "MRAM"}],
        {"generated_at_utc": "2026-04-30T15:00:00Z"},
        tmp_path,
        deep_cfg={"runner_path": str(runner), "timeout_seconds": 10, "poll_seconds": 1},
    )
    assert result.success
    assert result.route_chosen == "deep_mini"
    assert result.summary_path
    assert result.executor_output_path
    assert result.structured_packet_path
    assert result.structured_packet
    assert result.structured_packet["best_pick"] == "MRAM"


def test_run_governed_deep_mini_rejects_unparsed_success_output(tmp_path, monkeypatch):
    runner = tmp_path / "deep-research-runner"
    runner.write_text("#!/bin/sh\n")

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, cwd, capture_output, text, timeout, check):
        summary_path = command[command.index("--summary-json") + 1]
        with open(summary_path, "w") as f:
            json.dump({"success": True, "route_chosen": "deep_mini", "executor_output": "Looks interesting but no structured pick."}, f)
        return Completed()

    monkeypatch.setattr("src.workflows.deep_mini_bridge.subprocess.run", fake_run)
    result = run_governed_deep_mini(
        [{"ticker": "MRAM"}],
        {"generated_at_utc": "2026-04-30T15:00:00Z"},
        tmp_path,
        deep_cfg={"runner_path": str(runner), "timeout_seconds": 10, "poll_seconds": 1},
    )
    assert result.success
    assert result.structured_packet is None
    assert result.structured_packet_path is None


def test_deep_mini_artifact_names_do_not_collide_same_second(tmp_path):
    first = write_deep_mini_input([{"ticker": "MRAM"}], {}, tmp_path)
    second = write_deep_mini_input([{"ticker": "INFQ"}], {}, tmp_path)
    assert first != second
    assert first.exists()
    assert second.exists()


def test_fallback_packet_does_not_name_best_pick_without_execution_eligible():
    ranked = [
        {
            "ticker": "MRAM",
            "cluster": {"primary_ticker": "MRAM", "claim_summary": "MRAM wins contract"},
            "research_scorecard": {"story_stage": "early", "freshness_score": 8.8, "attention_acceleration_score": 3.2, "crowding_score": 2.0},
            "story_stage": "early",
        }
    ]
    packet = build_fallback_best_pick_packet(ranked, [], generated_at_utc="2026-04-30T15:00:00Z")
    assert packet.best_pick is None
    assert packet.research_leader == "MRAM"
    assert "no_execution_eligible_candidate" in packet.caveats
    assert packet.suggested_buy_zone is None
