from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


LIVE_RUNTIME_FILES = [
    "configs/live.yaml",
    "scripts/run_final_live_arming_gate.sh",
    "scripts/run_live_opening_trade_ready.sh",
    "scripts/run_opening_bell_live_monitor.sh",
    "scripts/run_live_force_flat.sh",
    "ops/progress/broker_safe_systems_check.py",
]


def test_live_runtime_files_do_not_select_webull():
    joined = "\n".join((ROOT / rel).read_text() for rel in LIVE_RUNTIME_FILES)

    assert "provider: webull" not in joined
    assert "base_url: https://api.webull.com" not in joined
    assert "WEBULL_ENVIRONMENT=live" not in joined
    assert "missing_webull_trade_credentials" not in joined


def test_webull_adapters_are_legacy_only_not_live_selected():
    adapter_paths = [
        ROOT / "src" / "adapters" / "webull_trade.py",
        ROOT / "src" / "adapters" / "webull_md.py",
    ]
    assert all(path.exists() for path in adapter_paths)

    live_text = (ROOT / "configs" / "live.yaml").read_text()
    assert "webull" not in live_text.lower()
