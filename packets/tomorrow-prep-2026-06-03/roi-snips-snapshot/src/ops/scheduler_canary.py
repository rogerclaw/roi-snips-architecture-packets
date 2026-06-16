from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _write_probe(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ok": True, "generated_at_utc": datetime.now(timezone.utc).isoformat()}))
        ok = path.exists()
        if ok:
            path.unlink()
        return ok
    except Exception:
        return False


def build_scheduler_canary(
    *,
    root: Path = ROOT,
    shell_invoked: bool = True,
    execute_validation: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    failure_reasons: list[str] = []
    venv_python = root / ".venv" / "bin" / "python"
    validation_script = root / "scripts" / "run_next_open_shadow_validation.py"

    if not shell_invoked:
        failure_reasons.append("shell_not_invoked")
    if not root.exists():
        failure_reasons.append("repo_root_missing")
    if not venv_python.exists():
        failure_reasons.append("venv_python_missing")

    python_version = None
    python_ok = False
    if venv_python.exists():
        completed = subprocess.run([str(venv_python), "--version"], cwd=root, capture_output=True, text=True, check=False)
        python_version = (completed.stdout or completed.stderr).strip()
        python_ok = completed.returncode == 0
    if not python_ok:
        failure_reasons.append("python_version_failed")

    import_smoke_ok = False
    if venv_python.exists():
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        completed = subprocess.run(
            [str(venv_python), "-c", "import src.ops.artifact_gate; print('ok')"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        import_smoke_ok = completed.returncode == 0
    if not import_smoke_ok:
        failure_reasons.append("python_import_smoke_failed")

    can_write_reports = _write_probe(root / "reports" / "readiness" / ".canary_write_probe.json")
    can_write_runs = _write_probe(root / "runs" / ".canary_write_probe.json")
    if not can_write_reports:
        failure_reasons.append("cannot_write_reports")
    if not can_write_runs:
        failure_reasons.append("cannot_write_runs")

    no_order_env_forced_false = True
    can_execute_validation_script = validation_script.exists()
    validation_result: dict[str, Any] | None = None
    if not can_execute_validation_script:
        failure_reasons.append("validation_script_missing")
    elif execute_validation and venv_python.exists():
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        env["ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION"] = "false"
        env["ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION"] = "false"
        env["ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT"] = "true"
        env["ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW"] = "true"
        completed = subprocess.run(
            [str(venv_python), str(validation_script), "--skip-stream"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        validation_result = {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
        if completed.returncode != 0:
            failure_reasons.append("validation_script_skip_stream_failed")

    status = "PASS" if not failure_reasons else "FAIL"
    return {
        "status": status,
        "shell_invoked": shell_invoked,
        "shell_capable": shell_invoked,
        "repo_root_ok": root.exists(),
        "python_ok": python_ok,
        "python_version": python_version,
        "venv_ok": venv_python.exists(),
        "import_smoke_ok": import_smoke_ok,
        "can_execute_validation_script": can_execute_validation_script,
        "validation_executed": bool(execute_validation and can_execute_validation_script and venv_python.exists()),
        "can_write_reports": can_write_reports,
        "can_write_runs": can_write_runs,
        "broker_access_attempted": False,
        "orders_allowed": False,
        "orders_submitted": False,
        "no_order_env_forced_false": no_order_env_forced_false,
        "failure_reasons": failure_reasons,
        "validation_result": validation_result,
        "human_summary": "Scheduler canary passed with brokerless no-order validation proof." if status == "PASS" else "Scheduler canary failed: " + ", ".join(failure_reasons),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_scheduler_canary(path: Path, *, root: Path = ROOT, shell_invoked: bool = True, execute_validation: bool = True) -> dict[str, Any]:
    report = build_scheduler_canary(root=root, shell_invoked=shell_invoked, execute_validation=execute_validation)
    report["proof_path"] = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Write Roi Snips brokerless scheduler canary proof.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute-validation", dest="execute_validation", action="store_true")
    parser.add_argument(
        "--skip-validation",
        dest="execute_validation",
        action="store_false",
        help="Test/debug-only escape hatch. Default canary execution runs brokerless --skip-stream validation.",
    )
    parser.set_defaults(execute_validation=True)
    parser.add_argument("--no-shell", action="store_true", help="Test/failure mode: mark shell as unavailable.")
    args = parser.parse_args()

    report = write_scheduler_canary(
        Path(args.output),
        root=ROOT,
        shell_invoked=not args.no_shell,
        execute_validation=args.execute_validation,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
