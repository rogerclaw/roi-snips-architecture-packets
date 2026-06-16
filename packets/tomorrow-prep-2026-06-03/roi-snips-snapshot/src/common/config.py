from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIVE_CONFIG_PATH = REPO_ROOT / "configs" / "live.yaml"
DEFAULT_PAPER_CONFIG_PATH = REPO_ROOT / "configs" / "paper.yaml"
DEFAULT_WORKFLOW_CONFIG_PATH = REPO_ROOT / "config" / "workflow.yaml"


@lru_cache(maxsize=1)
def repo_root() -> Path:
    return REPO_ROOT


@lru_cache(maxsize=1)
def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    env_path = Path(path) if path else (repo_root() / ".env")
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
        if key:
            loaded[key] = value
    return loaded


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"yaml config must be a mapping: {path}")
    return data


def _configured_path(explicit: str | Path | None, env_names: tuple[str, ...], default: Path) -> Path:
    if explicit:
        return Path(explicit)
    for env_name in env_names:
        value = os.getenv(env_name, "").strip()
        if value:
            return Path(value)
    return default


@lru_cache(maxsize=4)
def load_live_config(path: str | Path | None = None) -> dict[str, Any]:
    load_env_file()
    cfg_path = _configured_path(path, ("ROI_SNIPS_CONFIG_PATH", "ROI_SNIPS_LIVE_CONFIG_PATH"), DEFAULT_LIVE_CONFIG_PATH)
    return _load_yaml_mapping(cfg_path)


@lru_cache(maxsize=4)
def load_workflow_config(path: str | Path | None = None) -> dict[str, Any]:
    load_env_file()
    cfg_path = _configured_path(path, ("ROI_SNIPS_WORKFLOW_CONFIG_PATH",), DEFAULT_WORKFLOW_CONFIG_PATH)
    return _load_yaml_mapping(cfg_path)


def risk_config_for_validation(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_live_config()
    risk = cfg.get("risk") or {}
    strategy = cfg.get("strategy") or {}
    bankroll = cfg.get("bankroll") or {}
    opening_drive = strategy.get("opening_drive") or {}
    return {
        "initial_notional_min_usd": risk.get("initial_notional_usd_min", risk.get("initial_notional_min_usd", 50)),
        "initial_notional_max_usd": risk.get("initial_notional_usd_max", risk.get("initial_notional_max_usd", 250)),
        "max_trade_risk_usd": risk.get("max_trade_risk_usd", bankroll.get("max_open_risk_usd_normal", 80)),
        "max_spread_bps": risk.get("max_spread_bps", 60),
        "max_slippage_bps": risk.get("max_slippage_bps", 30),
        "max_open_positions": strategy.get("max_open_positions", 1),
        "opening_drive_max_spread_bps": risk.get("opening_drive_max_spread_bps", opening_drive.get("max_spread_bps", risk.get("max_spread_bps", 60))),
        "opening_drive_max_slippage_bps": risk.get("opening_drive_max_slippage_bps", opening_drive.get("max_slippage_bps", risk.get("max_slippage_bps", 30))),
        "opening_drive_max_trade_risk_usd": risk.get("opening_drive_max_trade_risk_usd", opening_drive.get("risk_budget_usd", bankroll.get("max_open_risk_usd_normal", 80))),
        "opening_drive_notional_usd_max": risk.get("opening_drive_notional_usd_max", opening_drive.get("notional_cap_usd", risk.get("initial_notional_usd_max", risk.get("initial_notional_max_usd", 250)))),
        "opening_drive_min_first_minute_volume": risk.get("opening_drive_min_first_minute_volume", opening_drive.get("min_first_minute_volume", 0)),
        "opening_drive_min_first_minute_dollar_volume": risk.get("opening_drive_min_first_minute_dollar_volume", opening_drive.get("min_first_minute_dollar_volume", 0)),
        "opening_drive_max_chase_pct": risk.get("opening_drive_max_chase_pct", opening_drive.get("max_chase_pct_above_reference", 0)),
        "opening_drive_min_close_in_range_pct": risk.get("opening_drive_min_close_in_range_pct", opening_drive.get("min_close_in_range_pct", 0)),
    }


def controls_paths(cfg: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = cfg or load_live_config()
    controls = cfg.get("controls") or {}
    return {
        "kill_switch": Path(controls.get("kill_switch_file", repo_root() / "state" / "KILL_SWITCH")),
        "live_armed": Path(controls.get("live_armed_file", repo_root() / "state" / "LIVE_ARMED")),
        "disable_entries": Path(controls.get("disable_entries_file", repo_root() / "state" / "DISABLE_NEW_ENTRIES")),
        "telegram_offset": Path(controls.get("telegram_offset_file", repo_root() / "state" / "telegram_offset.txt")),
        "proposals_dir": Path(controls.get("proposals_dir", repo_root() / "state" / "proposals")),
        "operator_events_dir": Path(controls.get("operator_events_dir", repo_root() / "state" / "operator_events")),
    }
