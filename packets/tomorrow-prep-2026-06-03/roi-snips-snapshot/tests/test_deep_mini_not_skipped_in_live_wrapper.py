import os
import shutil
import subprocess

from src.workflows.deep_mini_bridge import repo_root


def test_live_wrapper_defaults_to_deep_mini_primary_with_grok_heat_layer() -> None:
    body = (repo_root() / "scripts" / "run_live_trade_ready_premarket.sh").read_text()

    assert 'ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"' in body
    assert "ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH" in body
    assert "ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH" in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false' in body
    assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true' in body
    assert 'ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS:-1800' in body
    assert "LIVE_READINESS_RC" in body
    assert "premarket_start_latest.status.json" in body
    assert "premarket_research_continues;final_arming_gate_enforces_go_no_go" in body
    assert "check_grok_research_readiness.sh" in body
    assert "GROK_READINESS_RC" in body
    assert "optional_grok_readiness_must_not_block_deep_mini_primary_selector" in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH" = "true"' in body
    assert "-m src.workflows.grok_research_pipeline" in body
    assert "-m src.workflows.research_pipeline" in body
    assert "GROK_RESEARCH_RC" in body
    assert "DEEP_RESEARCH_RC" in body
    assert "grok_research_only_feeds_deep_mini;final_arming_gate_enforces_deep_mini_ticket" in body
    assert "deep_mini_primary_live_selector;final_arming_gate_enforces_deep_mini_ticket" in body


def test_skip_deep_mini_paths_are_labeled_smoke_not_live() -> None:
    root = repo_root()
    for relative in ["scripts/run_next_open_shadow_validation.py", "scripts/run_mechanical_checks.sh"]:
        body = (root / relative).read_text()
        assert "--skip-deep-mini" in body
        assert "SMOKE_SKIP_DEEP_MINI_NOT_FOR_LIVE_SELECTION" in body


def test_optional_grok_readiness_failure_still_runs_deep_mini_research(tmp_path) -> None:
    root = tmp_path
    (root / "scripts").mkdir()
    shutil.copy(repo_root() / "scripts" / "run_live_trade_ready_premarket.sh", root / "scripts" / "run_live_trade_ready_premarket.sh")
    (root / "scripts" / "run_live_trade_ready_premarket.sh").chmod(0o755)
    check = root / "scripts" / "check_grok_research_readiness.sh"
    check.write_text("#!/usr/bin/env bash\nprintf '{\"status\":\"FAIL\"}\\n'\nexit 1\n")
    check.chmod(0o755)
    stub_python = root / "python-stub"
    stub_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--version\" ]]; then echo 'Python stub'; exit 0; fi\n"
        "if [[ \"$1\" == \"-m\" ]]; then echo \"$2\" >> \"$ROI_SNIPS_STUB_MODULE_LOG\"; fi\n"
        "printf '{\"status\":\"stub\"}\\n'\n"
        "exit 0\n"
    )
    stub_python.chmod(0o755)
    module_log = root / "module.log"
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_BIN": str(stub_python),
            "ROI_SNIPS_STUB_MODULE_LOG": str(module_log),
            "ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH": "false",
        }
    )

    completed = subprocess.run(
        [str(root / "scripts" / "run_live_trade_ready_premarket.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    modules = module_log.read_text().splitlines()
    assert "src.workflows.grok_research_pipeline" in modules
    assert "src.workflows.research_pipeline" in modules
    assert "src.workflows.premarket_pipeline" in modules
    status = (root / "reports" / "live_monitor" / "live_trade_ready" / "grok_research_canary_latest.status.json").read_text()
    assert '"exit_code":1' in status
    assert "optional_grok_readiness_must_not_block_deep_mini_primary_selector" in status
    start_status = (root / "reports" / "live_monitor" / "live_trade_ready" / "premarket_start_latest.status.json").read_text()
    assert '"status":"started"' in start_status


def test_required_grok_readiness_failure_stops_before_deep_mini_research(tmp_path) -> None:
    root = tmp_path
    (root / "scripts").mkdir()
    shutil.copy(repo_root() / "scripts" / "run_live_trade_ready_premarket.sh", root / "scripts" / "run_live_trade_ready_premarket.sh")
    (root / "scripts" / "run_live_trade_ready_premarket.sh").chmod(0o755)
    check = root / "scripts" / "check_grok_research_readiness.sh"
    check.write_text("#!/usr/bin/env bash\nprintf '{\"status\":\"FAIL\"}\\n'\nexit 1\n")
    check.chmod(0o755)
    stub_python = root / "python-stub"
    stub_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"-m\" ]]; then echo \"$2\" >> \"$ROI_SNIPS_STUB_MODULE_LOG\"; fi\n"
        "printf '{\"status\":\"stub\"}\\n'\n"
        "exit 0\n"
    )
    stub_python.chmod(0o755)
    module_log = root / "module.log"
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_BIN": str(stub_python),
            "ROI_SNIPS_STUB_MODULE_LOG": str(module_log),
            "ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH": "true",
        }
    )

    completed = subprocess.run(
        [str(root / "scripts" / "run_live_trade_ready_premarket.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    modules = module_log.read_text().splitlines()
    assert "src.workflows.live_readiness" in modules
    assert "src.workflows.research_pipeline" not in modules
