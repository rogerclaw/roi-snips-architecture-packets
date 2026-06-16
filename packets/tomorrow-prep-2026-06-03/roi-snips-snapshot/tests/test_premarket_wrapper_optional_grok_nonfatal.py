from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "reports" / "live_monitor" / "live_trade_ready"
LOCK_DIR = ROOT / "state" / "live_trade_ready_premarket.lock"


def _clean_status_files() -> None:
    shutil.rmtree(LOCK_DIR, ignore_errors=True)
    for name in [
        "grok_research_canary_latest.status.json",
        "grok_heat_latest.status.json",
        "research_latest.status.json",
        "premarket_latest.status.json",
        "premarket_wrapper_final_2099-06-01.json",
    ]:
        (LOG_DIR / name).unlink(missing_ok=True)


def _run_wrapper(tmp_path: Path, *, grok_rc: int, grok_required: bool, research_rc: int = 0) -> subprocess.CompletedProcess[str]:
    _clean_status_files()
    fake_grok = tmp_path / "fake_grok.sh"
    fake_grok.write_text(f"#!/usr/bin/env bash\nprintf '{{\"status\":\"fake\"}}\\n'\nexit {grok_rc}\n")
    fake_grok.chmod(0o700)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "ROI_SNIPS_TRADE_DATE": "2099-06-01",
            "ROI_SNIPS_GROK_READINESS_SCRIPT": str(fake_grok),
            "ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH": "true" if grok_required else "false",
            "ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH": "true",
            "ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION": "false",
            "ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION": "false",
            "ROI_SNIPS_TEST_STUB_GROK_PIPELINE": "true",
            "ROI_SNIPS_TEST_STUB_RESEARCH_PIPELINE": "true",
            "ROI_SNIPS_TEST_STUB_RESEARCH_PIPELINE_EXIT_CODE": str(research_rc),
            "ROI_SNIPS_TEST_STUB_PREMARKET_PIPELINE": "true",
        }
    )
    return subprocess.run(
        ["bash", "scripts/run_live_trade_ready_premarket.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_optional_grok_failure_still_reaches_deep_mini(tmp_path: Path) -> None:
    completed = _run_wrapper(tmp_path, grok_rc=1, grok_required=False)

    assert completed.returncode == 0, completed.stderr
    assert _read_json(LOG_DIR / "grok_research_canary_latest.status.json")["status"] == "WARN_CONTINUE"
    research_status = _read_json(LOG_DIR / "research_latest.status.json")
    assert research_status["step"] == "governed_deep_research_pipeline"
    assert research_status["exit_code"] == 0
    assert research_status["deep_mini_required"] is True
    assert research_status["deep_mini_reached"] is True
    assert (LOG_DIR / "premarket_latest.json").exists()
    assert _read_json(LOG_DIR / "premarket_wrapper_final_2099-06-01.json")["deep_mini_reached"] is True


def test_required_grok_failure_stops_before_deep_mini(tmp_path: Path) -> None:
    completed = _run_wrapper(tmp_path, grok_rc=1, grok_required=True)

    assert completed.returncode != 0
    assert _read_json(LOG_DIR / "grok_research_canary_latest.status.json")["status"] == "FAIL_REQUIRED_GROK_UNAVAILABLE"
    assert not (LOG_DIR / "research_latest.status.json").exists()


def test_required_deep_mini_failure_is_fatal(tmp_path: Path) -> None:
    completed = _run_wrapper(tmp_path, grok_rc=0, grok_required=False, research_rc=7)

    assert completed.returncode == 7
    research_status = _read_json(LOG_DIR / "research_latest.status.json")
    assert research_status["status"] == "FAIL"
    assert research_status["note"] == "deep_mini_required_pipeline_failed"
