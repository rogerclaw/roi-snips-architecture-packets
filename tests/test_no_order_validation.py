import importlib.util
import sys
from pathlib import Path

from src.workflows.opening_stream_supervisor import replay_opening_stream


def test_no_order_replay_never_marks_orders_submitted(tmp_path) -> None:
    result = replay_opening_stream(
        {"ticker": "INFQ"},
        [{"type": "quote", "symbol": "INFQ", "timestamp": "2026-05-27T13:30:10+00:00", "bid": 12.0, "ask": 12.02}],
        {},
        output_dir=tmp_path,
    )

    assert result["orders_submitted"] is False
    assert result["stream_capture_started"] is True
    assert result["proposal_count"] == 0


def test_next_open_shadow_validation_skips_broker_readiness_in_brokerless_mode(monkeypatch, capsys) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_next_open_shadow_validation.py"
    spec = importlib.util.spec_from_file_location("run_next_open_shadow_validation", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    calls: list[str] = []

    def fake_run_step(name, command, *, timeout, env):
        calls.append(name)
        return {
            "name": name,
            "status": "ok",
            "returncode": 0,
            "timeout_seconds": timeout,
            "started_at_utc": "2026-05-27T15:00:00+00:00",
            "finished_at_utc": "2026-05-27T15:00:01+00:00",
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(module, "_latest_stream_summary", lambda trade_date: {"ok": False, "reason": "stream_skipped"})
    monkeypatch.setattr(sys, "argv", ["run_next_open_shadow_validation.py", "--skip-stream"])

    assert module.main() == 0
    payload = capsys.readouterr().out

    assert "live_readiness" not in calls
    assert "opening_bell_readiness_allow_non_green" not in calls
    assert "broker_readiness_skipped_for_brokerless_shadow" in payload
    assert "opening_bell_readiness_skipped_for_brokerless_shadow" in payload
