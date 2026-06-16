from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import controls_paths, load_live_config


def _parse_clock(value: str) -> time:
    parts = [int(p) for p in str(value).split(":")]
    if len(parts) == 2:
        return time(parts[0], parts[1], 0)
    if len(parts) == 3:
        return time(parts[0], parts[1], parts[2])
    raise ValueError(f"invalid clock value: {value}")


def _session_now(cfg: dict[str, Any], now: datetime | None = None) -> datetime:
    session = cfg.get("session") or {}
    tz = ZoneInfo(session.get("timezone", "America/New_York"))
    if now is None:
        return datetime.now(tz)
    return now.astimezone(tz)


def _time_reached(current: datetime, hhmmss: str) -> bool:
    return current.time() >= _parse_clock(hhmmss)


def session_phase(cfg: dict[str, Any] | None = None, now: datetime | None = None) -> str:
    cfg = cfg or load_live_config()
    current = _session_now(cfg, now)
    session = cfg.get("session") or cfg.get("schedule") or {}
    first_entry = session.get("first_new_entry_et", session.get("confirmation_backup_start", "09:30:00"))
    last_entry = session.get("last_new_entry_et", session.get("no_new_symbols_after", "11:00:00"))
    force_flat = session.get("force_flat_all_et", session.get("force_flat_at", "15:45:00"))

    if _time_reached(current, force_flat):
        return "FORCE_FLAT"
    if not _time_reached(current, first_entry):
        return "PRE_ENTRY"
    if _time_reached(current, last_entry):
        return "MANAGE_ONLY"
    return "ENTRY_WINDOW"


def in_entry_window(cfg: dict[str, Any] | None = None, now: datetime | None = None) -> bool:
    return session_phase(cfg, now) == "ENTRY_WINDOW"


def should_force_flat(cfg: dict[str, Any] | None = None, now: datetime | None = None) -> bool:
    return session_phase(cfg, now) == "FORCE_FLAT"


def _flag_path(name: str, cfg: dict[str, Any] | None = None) -> Path:
    return controls_paths(cfg)[name]


def is_flag_active(name: str, cfg: dict[str, Any] | None = None) -> bool:
    path = _flag_path(name, cfg)
    if not path.exists():
        return False
    try:
        raw = path.read_text().strip().lower()
    except Exception:
        return True
    if raw in {"0", "false", "off", "no", "inactive"}:
        return False
    return True


def activate_flag(name: str, reason: str = "", cfg: dict[str, Any] | None = None) -> Path:
    path = _flag_path(name, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reason.strip() + "\n")
    return path


def clear_flag(name: str, cfg: dict[str, Any] | None = None) -> None:
    path = _flag_path(name, cfg)
    if path.exists():
        path.unlink()


def active_guards(cfg: dict[str, Any] | None = None) -> dict[str, bool]:
    cfg = cfg or load_live_config()
    return {
        "live_armed": is_flag_active("live_armed", cfg),
        "kill_switch": is_flag_active("kill_switch", cfg),
        "disable_entries": is_flag_active("disable_entries", cfg),
        "in_entry_window": in_entry_window(cfg),
        "force_flat": should_force_flat(cfg),
    }
