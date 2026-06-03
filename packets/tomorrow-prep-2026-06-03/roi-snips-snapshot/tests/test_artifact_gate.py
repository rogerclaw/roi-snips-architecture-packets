from pathlib import Path
from types import SimpleNamespace

import src.ops.scheduler_canary as scheduler_canary
from src.ops.artifact_gate import evaluate_morning_readiness
from src.ops.morning_control_plane import build_morning_readiness
from src.ops.scheduler_canary import build_scheduler_canary


def _ready_artifacts() -> dict:
    return {
        "canary": {"status": "PASS"},
        "same_day_packet": {
            "orders_submitted": False,
            "orders_previewed": False,
            "orders_canceled": False,
            "broker_account_inspected": False,
            "broker_orders_inspected": False,
            "broker_positions_inspected": False,
        },
        "source_lane_status": {"source_breadth_status": "OK"},
        "stream_summary": {
            "stream_captured": True,
            "stream_capture_completed": True,
            "opening_burst_window_covered": True,
            "continuation_window_covered": True,
        },
        "symbols": ["ABCD"],
        "broad_discovery": {"raw_candidate_count": 50, "status": "OK"},
        "candidate_tournament": {"same_style_backup_pool_ok": True, "backup_pool_status": "OK"},
        "research_war_room": {"status": "OK"},
    }


def test_shell_canary_fails_if_no_shell() -> None:
    report = build_scheduler_canary(root=Path(__file__).resolve().parents[1], shell_invoked=False, execute_validation=False)

    assert report["status"] == "FAIL"
    assert "shell_not_invoked" in report["failure_reasons"]
    assert report["broker_access_attempted"] is False
    assert report["orders_submitted"] is False
    assert report["no_order_env_forced_false"] is True


def test_scheduler_canary_defaults_to_brokerless_skip_stream_validation(tmp_path, monkeypatch) -> None:
    root = tmp_path
    venv_python = root / ".venv" / "bin" / "python"
    validation = root / "scripts" / "run_next_open_shadow_validation.py"
    venv_python.parent.mkdir(parents=True)
    validation.parent.mkdir(parents=True)
    venv_python.write_text("")
    validation.write_text("")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(scheduler_canary.subprocess, "run", fake_run)

    report = build_scheduler_canary(root=root)

    assert report["validation_executed"] is True
    assert report["no_order_env_forced_false"] is True
    assert report["broker_access_attempted"] is False
    assert report["orders_submitted"] is False
    assert any("run_next_open_shadow_validation.py" in str(args) and "--skip-stream" in args for args, _kwargs in calls)


def test_launchd_templates_exist_and_stay_brokerless_no_order() -> None:
    root = Path(__file__).resolve().parents[1]
    canary = root / "ops" / "launchd" / "com.roisnips.canary.plist.template"
    research = root / "ops" / "launchd" / "com.roisnips.research-war-room.plist.template"
    validation = root / "ops" / "launchd" / "com.roisnips.noorder-validation.plist.template"

    for path in [canary, research, validation]:
        body = path.read_text()
        assert "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" in body
        assert "ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION" in body
        assert "false" in body
        assert "ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW" in body
        assert "true" in body
    assert "roi_snips_morning_canary.sh" in canary.read_text()
    assert "run_research_war_room.sh" in research.read_text()
    assert "run_morning_end_to_end_no_order_validation.sh" in validation.read_text()


def test_openclaw_cron_ok_without_artifact_is_not_ready() -> None:
    artifacts = _ready_artifacts()
    artifacts["canary"] = {}

    result = evaluate_morning_readiness(artifacts)

    assert result.ready_for_no_order is False
    assert result.final_status == "INTERNAL_FAILURE"
    assert "canary_missing_or_failed" in result.failure_reasons


def test_missing_same_day_packet_fails() -> None:
    artifacts = _ready_artifacts()
    artifacts["same_day_packet"] = {}

    result = evaluate_morning_readiness(artifacts)

    assert result.ready_for_no_order is False
    assert "same_day_packet_missing" in result.failure_reasons


def test_no_stream_symbols_fails() -> None:
    artifacts = _ready_artifacts()
    artifacts["symbols"] = []

    result = evaluate_morning_readiness(artifacts)

    assert result.ready_for_no_order is False
    assert "stream_symbols_missing" in result.failure_reasons


def test_brokerless_mode_cannot_inspect_broker() -> None:
    artifacts = _ready_artifacts()
    artifacts["same_day_packet"]["broker_positions_inspected"] = True

    result = evaluate_morning_readiness(artifacts)

    assert result.ready_for_no_order is False
    assert "broker_inspected_in_brokerless_mode" in result.failure_reasons


def test_no_order_mode_cannot_submit_preview_or_cancel_orders() -> None:
    artifacts = _ready_artifacts()
    artifacts["same_day_packet"]["orders_previewed"] = True

    result = evaluate_morning_readiness(artifacts)

    assert result.ready_for_no_order is False
    assert "order_action_in_no_order_mode" in result.failure_reasons


def test_artifact_gate_must_pass_before_ready_message() -> None:
    result = evaluate_morning_readiness(_ready_artifacts())

    assert result.final_status == "READY"
    assert result.ready_for_no_order is True
    assert result.ready_for_live is False
    assert result.ready_for_paper is False


def test_missing_stream_when_required_fails() -> None:
    artifacts = _ready_artifacts()
    artifacts["stream_summary"] = {"reason": "stream_skipped", "stream_captured": False}

    result = evaluate_morning_readiness(artifacts)

    assert result.ready_for_no_order is False
    assert "required_stream_summary_missing_or_skipped" in result.failure_reasons


def test_connectivity_only_cannot_claim_market_open_readiness() -> None:
    artifacts = _ready_artifacts()
    artifacts["stream_summary"]["proof_scope"] = "CONNECTIVITY_ONLY"

    result = evaluate_morning_readiness(artifacts, requested_proof_scope="MARKET_OPEN_READINESS")

    assert result.ready_for_no_order is False
    assert result.final_status == "CONNECTIVITY_ONLY"
    assert "connectivity_only_claimed_as_market_open_readiness" in result.failure_reasons


def test_morning_control_plane_reads_artifacts_from_paths(tmp_path) -> None:
    trade_date = "2026-05-28"
    canary = tmp_path / "canary.json"
    packet = tmp_path / "packet.json"
    lanes = tmp_path / "lanes.json"
    stream = tmp_path / "stream.json"
    canary.write_text('{"status":"PASS"}')
    packet.write_text(
        '{"orders_submitted":false,"orders_previewed":false,"orders_canceled":false,'
        '"broker_account_inspected":false,"broker_orders_inspected":false,'
        '"broker_positions_inspected":false,"symbols":["ABCD"],'
        '"broad_discovery":{"raw_candidate_count":50,"status":"OK"},'
        '"candidate_tournament":{"same_style_backup_pool_ok":true,"backup_pool_status":"OK"},'
        '"research_war_room":{"status":"OK"}}'
    )
    lanes.write_text('{"source_breadth_status":"OK"}')
    stream.write_text('{"stream_captured":true,"stream_capture_completed":true,"opening_burst_window_covered":true,"continuation_window_covered":true}')

    result = build_morning_readiness(
        trade_date=trade_date,
        root=tmp_path,
        canary_path=canary,
        same_day_packet_path=packet,
        source_lane_status_path=lanes,
        stream_summary_path=stream,
    )

    assert result["ready_for_no_order"] is True
    assert result["final_status"] == "READY"
