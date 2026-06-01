from pathlib import Path

from src.workflows.deep_mini_bridge import build_deep_mini_brief, load_grok_social_context, write_deep_mini_input


def test_shortlist_input_includes_grok_heat_and_web_verification(tmp_path):
    grok_dir = tmp_path / "grok"
    grok_dir.mkdir()
    (grok_dir / "x_heat_radar.json").write_text('{"stage":"grok_x_heat_radar","candidates":[{"ticker":"ABCD","attention_velocity_score":9}]}')
    (grok_dir / "web_verification.json").write_text('{"stage":"grok_web_verification","verified_candidates":[{"ticker":"ABCD","verified_catalyst":true}]}')
    (grok_dir / "challenger_notes.json").write_text('{"stage":"grok_challenger_notes","verdict":"PASS_ONLY_WITH_TAPE"}')

    context = {"grok_social_context": load_grok_social_context(tmp_path)}
    output_path = write_deep_mini_input([{"ticker": "ABCD"}], context, tmp_path / "deep_mini")
    canonical = Path(output_path).parent / "shortlist_input.md"
    body = canonical.read_text()

    assert "Grok/X Heat Radar and Web Verification Context" in body
    assert "grok_x_heat_radar" in body
    assert "grok_web_verification" in body
    assert "Charles stock-picking mandate" in body


def test_deep_mini_prompt_says_grok_cannot_authorize():
    brief = build_deep_mini_brief(
        [{"ticker": "ABCD"}],
        {"grok_social_context": {"can_authorize_live_trade": False, "artifacts": {}}},
    )

    assert "cannot authorize a live trade" in brief
    assert "Deep-mini must judge" in brief
