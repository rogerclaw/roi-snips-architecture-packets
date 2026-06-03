from datetime import datetime, timezone

from src.common.runtime_state import activate_flag, clear_flag, in_entry_window, is_flag_active, session_phase, should_force_flat


CFG = {
    "session": {
        "timezone": "America/New_York",
        "first_new_entry_et": "09:30",
        "last_new_entry_et": "11:00",
        "force_flat_all_et": "15:45",
    },
    "controls": {
        "kill_switch_file": "/tmp/roi-snips-test-kill",
        "disable_entries_file": "/tmp/roi-snips-test-disable",
        "telegram_offset_file": "/tmp/roi-snips-test-offset",
        "proposals_dir": "/tmp/roi-snips-test-proposals",
        "operator_events_dir": "/tmp/roi-snips-test-ops",
    },
}


def test_session_phase_entry_window():
    now = datetime(2026, 4, 14, 14, 0, tzinfo=timezone.utc)  # 10:00 ET
    assert session_phase(CFG, now) == "ENTRY_WINDOW"
    assert in_entry_window(CFG, now)


def test_session_phase_force_flat():
    now = datetime(2026, 4, 14, 20, 0, tzinfo=timezone.utc)  # 16:00 ET
    assert session_phase(CFG, now) == "FORCE_FLAT"
    assert should_force_flat(CFG, now)


def test_flag_activation_and_clear(tmp_path):
    cfg = {
        **CFG,
        "controls": {
            **CFG["controls"],
            "kill_switch_file": str(tmp_path / "kill"),
            "disable_entries_file": str(tmp_path / "disable"),
        },
    }
    activate_flag("kill_switch", reason="test", cfg=cfg)
    assert is_flag_active("kill_switch", cfg)
    clear_flag("kill_switch", cfg)
    assert not is_flag_active("kill_switch", cfg)


def test_live_armed_flag_is_reported_in_guards(tmp_path):
    from src.common.runtime_state import active_guards

    cfg = {
        **CFG,
        "controls": {
            **CFG["controls"],
            "live_armed_file": str(tmp_path / "live_armed"),
            "kill_switch_file": str(tmp_path / "kill"),
            "disable_entries_file": str(tmp_path / "disable"),
        },
    }
    assert active_guards(cfg)["live_armed"] is False
    activate_flag("live_armed", reason="armed for test", cfg=cfg)
    assert active_guards(cfg)["live_armed"] is True
